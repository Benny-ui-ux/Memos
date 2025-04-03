# Memos
A web-based note-taking/reminder service

UPDATES 04/03/2025:



Added notification feature to memo service: 

-Memos can now send notiications at a scheduled time through the Pushover app/API. To accomplish this, download the pushover app (or login on desktop) and set the API/User Key in your .env file. 



Added unique links to Journal/Notes:

-Notes and Journals are now placed into unique links using the python-slugify library. This keeps the pages organized and makes more room for more notes.



Added Javascript/html-typing compatibility for better functionality:

-You can now type notes using html tags for unique designs. You can even embed CSS if you want to style your notes!

-Javacript logic extends the form the more lines you make.

-Wrap highlighted text in "code" tags by highlighting (or ctrl + a) and then hitting (ctrl + ') for easy code tags (More hotkeys coming soon!)



Updated database to use MariaDB/MySQL:

-SQLAlchemy now makes queries using MariaDB/MySQL. I personally set it up to use Maria, but you can choose whichever you like. 



Updated Design with Bootstrap:

-Pages are now designed with Bootswatch Cyborg Theme. Much easier on the eyes than the blinding white. 

-Each data point (Memo Note and Journal) now appear left-to-right instead of top-to-bottom (unless on mobile) to make even more space to store your thoughts. 







