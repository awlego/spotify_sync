
# How it Works
1) Make last.fm account
2) Setup Spotify Scrobbling on last.fm
3) Listen to a few songs
4) Download csv file of your listening history
5) Setup the jupyter notebook
6) Run the jupyter notebook

## Downloading listening history
https://benjaminbenben.com/lastfm-to-csv/

Just enter your username and download the csv. Eventually I would like to automate this, but for now it's easy enough to manually download.

## Setup the Juypyter Notebook
To use with a virtual environment:
```
python3.10 -m venv env3.10
source env3.10/bin/activate    
pip install -r requirements.txt
ipython kernel install --user --name=env3.10
```

## Create .env file
make a `.env` file in the same directory as the jupyter notebook. See `.env.example` for the keys you will need.

## Run the notebook!
```
jupyter notebook
```
I recommend following along cell by cell, but you it should work if you press "run all". The first time might fail if you don't already have the playlist IDs in your environment variables, but there is a section you can run to create the playlists and print the IDs.
