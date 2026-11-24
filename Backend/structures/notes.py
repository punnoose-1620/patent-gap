"""
Notes model — annotations pinned to case UI sections.

Document shape:
  _id, case_id, section (object), section_key, note,
  created_on, created_by, last_updated, updated_by
"""
from datetime import datetime as dt

from database import (
    addDataById,
    connect_to_database,
    deleteDataById,
    getDataById,
    getDataByKeyValue,
    updateDataById,
)
from env_controller import getNotesDatabaseName

# Closed set of section types. Fields beyond ``type`` depend on the type.
SECTION_TYPES = frozenset({
    'description',
    'title',
    'inventors',
    'keywords',
    'context',
    'search_limitations',
    'claim',
    'product',
    'product_claim',
    'claim_chart',
    'claim_matrix',
})

# Types that require a claim / row index
_INDEX_TYPES = frozenset({
    'claim',
    'product_claim',
    'claim_chart',
    'claim_matrix',
})

# Types that require an infringement / product entry id
_ENTRY_TYPES = frozenset({
    'product',
    'product_claim',
    'claim_chart',
    'claim_matrix',
})

# Major UI sections for list fetches (no claim/row index required)
_MAJOR_CASE_TYPES = frozenset({
    'description',
    'title',
    'inventors',
    'keywords',
    'context',
    'search_limitations',
    'claim',
})
_MAJOR_PRODUCT_TYPES = frozenset({
    'product',
})

_indexes_ensured = False


def validate_note_content(note):
    """
    Ensure note text is non-empty and not stop-word-only / empty-vocabulary.

    Returns ``(ok, result)`` where ``result`` is the stripped text on success
    or an error message on failure.
    """
    if note is None:
        return False, 'note content is required'
    text = note.strip() if isinstance(note, str) else str(note).strip()
    if not text:
        return False, 'note content cannot be empty'
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        TfidfVectorizer(stop_words='english').fit_transform([text])
        return True, text
    except Exception:
        # Align with keyword extraction messaging when vocab is empty
        try:
            from data_processor import getEmbeddingOffline
            if getEmbeddingOffline(text) is None:
                return False, 'Note appears empty or contains only stop words'
        except Exception:
            pass
        return False, 'Note appears empty or contains only stop words'


def _collection():
    return connect_to_database()[getNotesDatabaseName()]


def _now_iso():
    return dt.utcnow().isoformat() + 'Z'


def _ensure_indexes():
    """Unique note per (case_id, section_key). Safe to call repeatedly."""
    global _indexes_ensured
    if _indexes_ensured:
        return
    try:
        _collection().create_index(
            [('case_id', 1), ('section_key', 1)],
            unique=True,
            name='uniq_case_section',
        )
        _collection().create_index(
            [('case_id', 1), ('last_updated', -1)],
            name='case_last_updated',
        )
        _indexes_ensured = True
    except Exception as e:
        print(f'LOG: notes index ensure skipped/failed: {e}')


def normalize_section(section):
    """
    Validate and normalize a section locator.

    Returns a cleaned ``section`` dict, or raises ``ValueError``.
    """
    if not isinstance(section, dict):
        raise ValueError('section must be an object')

    raw_type = section.get('type')
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise ValueError('section.type is required')
    section_type = raw_type.strip()
    if section_type not in SECTION_TYPES:
        raise ValueError(
            f'Unsupported section.type={section_type!r}. '
            f'Allowed: {sorted(SECTION_TYPES)}'
        )

    normalized = {'type': section_type}

    if section_type in _ENTRY_TYPES:
        entry_id = section.get('entry_id')
        if entry_id is None or str(entry_id).strip() == '':
            raise ValueError(f'section.entry_id is required for type={section_type}')
        normalized['entry_id'] = str(entry_id).strip()

    if section_type in _INDEX_TYPES:
        if 'index' not in section or section.get('index') is None:
            raise ValueError(f'section.index is required for type={section_type}')
        try:
            normalized['index'] = int(section['index'])
        except (TypeError, ValueError) as e:
            raise ValueError(f'section.index must be an integer for type={section_type}') from e

    return normalized


def section_key(section):
    """
    Stable string key for uniqueness / lookup.

    Examples:
      description
      claim:1
      product:abc
      product_claim:abc:1
      claim_chart:abc:2
    """
    normalized = normalize_section(section)
    stype = normalized['type']
    if stype in _ENTRY_TYPES and stype in _INDEX_TYPES:
        return f"{stype}:{normalized['entry_id']}:{normalized['index']}"
    if stype in _ENTRY_TYPES:
        return f"{stype}:{normalized['entry_id']}"
    if stype in _INDEX_TYPES:
        return f"{stype}:{normalized['index']}"
    return stype


def create_note(case_id, user_id, section, note, upsert=False):
    """
    Create a note for a case section.

    If ``upsert=True`` and a note already exists for (case_id, section),
    updates that note instead.
    """
    if not case_id or not str(case_id).strip():
        return {'success': False, 'message': 'case_id is required'}
    if not user_id or not str(user_id).strip():
        return {'success': False, 'message': 'user_id is required'}
    if note is None or (isinstance(note, str) and note.strip() == ''):
        return {'success': False, 'message': 'note content is required'}

    try:
        normalized = normalize_section(section)
        key = section_key(normalized)
    except ValueError as e:
        return {'success': False, 'message': str(e)}

    _ensure_indexes()
    case_id = str(case_id).strip()
    user_id = str(user_id).strip()
    note_text = note if isinstance(note, str) else str(note)
    now = _now_iso()

    existing = get_note_for_section(case_id, normalized)
    if existing.get('success') and existing.get('note'):
        if not upsert:
            return {
                'success': False,
                'message': 'Note already exists for this section',
                'note_id': existing['note'].get('_id'),
            }
        return update_note(
            existing['note']['_id'],
            user_id,
            {'note': note_text},
        )

    note_data = {
        'case_id': case_id,
        'section': normalized,
        'section_key': key,
        'note': note_text,
        'created_on': now,
        'created_by': user_id,
        'last_updated': now,
        'updated_by': user_id,
    }
    added_id = addDataById(connect_to_database(), getNotesDatabaseName(), note_data)
    if isinstance(added_id, str) and 'DocumentCreationError' in added_id:
        return {
            'success': False,
            'message': 'Failed to create note',
            'error': added_id,
        }
    note_data['_id'] = added_id
    return {
        'success': True,
        'message': 'Note created successfully',
        'note_id': added_id,
        'note': note_data,
    }


def update_note(note_id, user_id, update_fields):
    """
    Update an existing note. Allowed fields: ``note`` (content).
    Permissions are intentionally generic for now.
    """
    if not note_id:
        return {'success': False, 'message': 'note_id is required'}
    if not user_id:
        return {'success': False, 'message': 'user_id is required'}
    if not isinstance(update_fields, dict) or not update_fields:
        return {'success': False, 'message': 'update_fields is required'}

    allowed = {}
    if 'note' in update_fields:
        content = update_fields['note']
        if content is None or (isinstance(content, str) and content.strip() == ''):
            return {'success': False, 'message': 'note content cannot be empty'}
        allowed['note'] = content if isinstance(content, str) else str(content)

    if not allowed:
        return {'success': False, 'message': 'No updatable fields provided (allowed: note)'}

    allowed['last_updated'] = _now_iso()
    allowed['updated_by'] = str(user_id).strip()

    updated = updateDataById(
        connect_to_database(),
        getNotesDatabaseName(),
        allowed,
        note_id,
    )
    if not updated:
        return {'success': False, 'message': 'Note not found or update failed'}

    refreshed = get_note_by_id(note_id)
    return {
        'success': True,
        'message': 'Note updated successfully',
        'note': refreshed.get('note'),
    }


def delete_note(note_id, user_id=None):
    """
    Delete a note by id. ``user_id`` reserved for future permission checks.
    """
    if not note_id:
        return {'success': False, 'message': 'note_id is required'}

    deleted = deleteDataById(connect_to_database(), getNotesDatabaseName(), note_id)
    if deleted is None or deleted is False:
        return {'success': False, 'message': 'Note not found or delete failed'}
    return {
        'success': True,
        'message': 'Note deleted successfully',
        'note_id': note_id,
    }


def get_note_by_id(note_id):
    if not note_id:
        return {'success': False, 'message': 'note_id is required'}
    document = getDataById(connect_to_database(), getNotesDatabaseName(), note_id)
    if document is None:
        return {'success': False, 'message': 'Note not found'}
    return {
        'success': True,
        'message': 'Note fetched successfully',
        'note': document,
    }


def get_note_for_section(case_id, section):
    """Fetch the single note for a case + section locator (if any)."""
    if not case_id:
        return {'success': False, 'message': 'case_id is required'}
    try:
        normalized = normalize_section(section)
        key = section_key(normalized)
    except ValueError as e:
        return {'success': False, 'message': str(e)}

    try:
        document = _collection().find_one({
            'case_id': str(case_id).strip(),
            'section_key': key,
        })
        if document and '_id' in document and hasattr(document['_id'], '__str__'):
            document['_id'] = str(document['_id'])
    except Exception as e:
        print(f'Error fetching note for section: {e}')
        return {'success': False, 'message': f'Failed to fetch note: {e}'}

    if document is None:
        return {'success': False, 'message': 'Note not found for section'}
    return {
        'success': True,
        'message': 'Note fetched successfully',
        'note': document,
    }


def get_notes_for_case(case_id):
    """Return all notes for a case (user-scoped query via case_id only)."""
    if not case_id:
        return {'success': False, 'message': 'case_id is required', 'notes': []}

    notes = getDataByKeyValue(
        connect_to_database(),
        getNotesDatabaseName(),
        'case_id',
        str(case_id).strip(),
    )
    return {
        'success': True,
        'message': 'Notes fetched successfully',
        'notes': notes or [],
    }


def normalize_major_section(section):
    """
    Validate a *major* section filter for list fetches.

    - Case-level types (description, title, claim, …): ``{type}`` only
    - Product panel: ``{type: "product", entry_id}`` — returns all notes
      for that entry (product / product_claim / claim_chart / claim_matrix)

    ``index`` is ignored when present.
    """
    if not isinstance(section, dict):
        raise ValueError('section must be an object')
    raw_type = section.get('type')
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise ValueError('section.type is required')
    section_type = raw_type.strip()

    if section_type in _MAJOR_CASE_TYPES:
        return {'type': section_type}

    if section_type in _MAJOR_PRODUCT_TYPES or section_type in _ENTRY_TYPES:
        # Allow product_claim / claim_chart as aliases for the product panel
        # when only entry_id is provided (major fetch ignores index).
        entry_id = section.get('entry_id')
        if entry_id is None or str(entry_id).strip() == '':
            raise ValueError('section.entry_id is required for product section fetches')
        return {
            'type': 'product',
            'entry_id': str(entry_id).strip(),
        }

    raise ValueError(
        f'Unsupported major section.type={section_type!r}. '
        f'Allowed: {sorted(_MAJOR_CASE_TYPES | _MAJOR_PRODUCT_TYPES)}'
    )


def get_notes_for_major_section(case_id, section):
    """
    Return all notes under a major UI section for a case.

    Examples:
      ``{type: "claim"}`` → every ref-claim note
      ``{type: "product", entry_id: "xyz"}`` → every note for that product hit
      ``{type: "description"}`` → description notes
    """
    if not case_id:
        return {'success': False, 'message': 'case_id is required', 'notes': []}
    try:
        major = normalize_major_section(section)
    except ValueError as e:
        return {'success': False, 'message': str(e), 'notes': []}

    query = {'case_id': str(case_id).strip()}
    if major['type'] == 'product':
        query['section.entry_id'] = major['entry_id']
    else:
        query['section.type'] = major['type']

    try:
        notes = list(_collection().find(query, max_time_ms=120000))
        for doc in notes:
            if '_id' in doc and hasattr(doc['_id'], '__str__'):
                doc['_id'] = str(doc['_id'])
    except Exception as e:
        print(f'Error fetching notes for major section: {e}')
        return {
            'success': False,
            'message': f'Failed to fetch notes: {e}',
            'notes': [],
        }

    return {
        'success': True,
        'message': 'Notes fetched successfully',
        'section': major,
        'notes': notes,
    }
