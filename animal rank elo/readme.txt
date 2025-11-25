This project is a fun little app that lets you decide which animal picture is cuter by comparing two images side by side. Every time you vote, the app uses the Elo rating system (the same thing used in chess rankings) to update each animal’s score, so the leaderboard keeps changing as you vote more. Adding images is super easy — you can drag and drop them straight into the app or pick them through a file dialog. The app even copies them into its own “project_images” folder so nothing breaks if you move or delete the original files.

The interface is simple: two pictures, buttons to vote, dislike, or mark a draw, and a status bar that tells you what’s happening. You can look at bigger versions of the images in a built-in viewer that lets you zoom, rotate, and inspect them properly. There’s also a gallery mode, a detailed match history, and a full leaderboard showing which animals are currently ruling the cuteness charts. You can save your whole session, load it later, or export the leaderboard as a CSV file. Overall, this app mixes GUI, images, and a cool rating system into something that’s actually fun to use and perfect for a project or personal experiment.



#Project Structure
project/
│
├── elo_animal_voter.py      # Main program
├── project_images/           # Managed images folder
│    └── (all copied images)
├── elo_animal_voter_db.json  # Optional save file
└── leaderboard_export.csv    # (If exported)

# Dependencies

Install required packages:

pip install pillow
pip install tkinterdnd2   # optional, enables drag & drop

 #How to Run
python elo_animal_voter.py


The app will launch with the full GUI.

# How It Works (Short Explanation)

Images stored internally as ImageRecord dataclasses

Elo rating updated using standard calculation:

Win = 1.0

Draw = 0.5

Loss = 0.0

Match recorded as MatchRecord

GUI triggers backend updates and refreshes the display