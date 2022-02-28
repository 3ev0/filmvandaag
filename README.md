
# How it works
Telegram bot that will tell you what's playing on your favourite streaming services.
It uses the site filmvandaag.nl as the source. 

The following commands are understood: 

### /new, nieuw
Show movies recently added to streaming services. 
Questions
- which service?

Output:
List of movies sorted by imdb-score
title year genre imdb-score link

###  /beste
Show the best movies filtered on criteria. 
Questions:
- which genres
- minimal imdb-score
- released year after

### /random, kiesmaar
Show a random recent movie of particular genre with a decent IMDB-score. 
Questions:
- Genre?