## List of ideas or functions to be completed : 

1. **AI Model** : Add an AI chatbot for users to interact with. Pass embeddings of user's cases and similar cases for user to ask queries about.
2. **Firebase** : Add a file to handle firebase notification connections and actual alert initiation.
3. **Document Separation** : Currently, all documents related to a case/patent have same categorization. Split it into technical documents and case files. Use only technical documents for similarity matching and alerts.
4. **Styling** : Current layout only serves as a working demo. Needs more thorough alterations for aesthetics and to be made more '__Unique__'
5. **Additional Sources** : Add more sources to mine patents and related documents from.
6. **Database Integration** : Firebase has been decided as the ideal database during initial phases. Once Otto is done with GCP account creation, create firebase Database and collections. Then connect using [`database.py`](./Backend/database.py)
7. **Analytics Integration** : GCP also allows for Firebase Analytics that needs to be connected and integrated thoroughly
8. **Alert Handlers** : Add Alert handlers to front end for proper alert messages


## Bugs to be Resolved : 

1. **Alert** : Patents/Cases with empty documents leads to empty embeddings. This triggers alerts for all users who have atleast one case/patent with empty documents. Add backup embedding calculation and avoid spam alerts.
2. 

## Research to be done

1. **Sources** : Perform more thorough research on more sources for patents globally and unique to target countries/regions
2. **Translations** : Many patents might be in other languages. Research ideal translation methods that would not be confusing in terms of embeddings
3. **AI Model** : Perform research on which AI LLM model from public domain would best serve our purpose as a chatbot guide for users.
