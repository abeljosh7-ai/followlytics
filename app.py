from flask import Flask, render_template, request
import re
import json
import zipfile
import io
import os

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

def extract_usernames(data):
    usernames = set()

    def scan(obj):
        if isinstance(obj, dict):
            href = obj.get("href", "")
            if isinstance(href, str) and "instagram.com" in href:
                clean_href = href.lower().replace("instagram.com/_u/", "instagram.com/")
                match = re.search(r'instagram\.com/([a-z0-9._]+)', clean_href)
                if match:
                    uname = match.group(1).strip()
                    if uname not in ['p', 'reel', 'stories', 'explore', 'tv', 'direct']:
                        usernames.add(uname)

            if "string_list_data" in obj:
                for item in obj["string_list_data"]:
                    if isinstance(item, dict) and "value" in item:
                        val = str(item["value"]).strip().lower()
                        if val and val != "_u" and not val.startswith("http"):
                            if re.fullmatch(r"[a-z0-9._]{1,30}", val):
                                usernames.add(val)

            for v in obj.values():
                if isinstance(v, (dict, list)):
                    scan(v)
        
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    scan(item)

    scan(data)
    
    junk_words = {
        "_u", "relationships_following", "relationships_followers", 
        "title", "value", "href", "timestamp", "string_list_data", 
        "instagrammer"
    }
    return {u for u in usernames if u not in junk_words}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["GET", "POST"])
def upload_data():
    if request.method == "POST":
        uploaded_file = request.files.get("instagram_file")

        if not uploaded_file or not uploaded_file.filename:
            return render_template("upload.html", message="Please select your Instagram ZIP file.")

        if not uploaded_file.filename.lower().endswith(".zip"):
            return render_template("upload.html", message="Please upload an Instagram ZIP file.")

        try:
            followers = set()
            following = set()
            follower_files = []
            following_files = []

            with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as archive:
                for filename in archive.namelist():
                    basename = os.path.basename(filename).lower()

                    if not basename.endswith(".json"):
                        continue

                    if re.fullmatch(r"followers(_\d+)?\.json", basename):
                        follower_files.append(filename)
                    elif basename == "following.json":
                        following_files.append(filename)

                for filename in follower_files:
                    data = json.loads(archive.read(filename).decode("utf-8-sig"))
                    followers.update(extract_usernames(data))

                for filename in following_files:
                    data = json.loads(archive.read(filename).decode("utf-8-sig"))
                    following.update(extract_usernames(data))

            if not follower_files or not following_files:
                return render_template("upload.html", message="Followers or following JSON files not found in ZIP.")

            if not followers or not following:
                return render_template("upload.html", message="Could not extract usernames from the data.")

            not_following_back = sorted(following - followers)
            followers_not_following_back = sorted(followers - following)
            mutual = sorted(followers & following)

            return render_template(
                "dashboard.html",
                followers_count=len(followers),
                following_count=len(following),
                not_following_back=not_following_back,
                followers_not_following_back=followers_not_following_back,
                mutual=mutual
            )

        except zipfile.BadZipFile:
            return render_template("upload.html", message="Invalid ZIP file. Please upload your original export.")
        except json.JSONDecodeError:
            return render_template("upload.html", message="Could not read an Instagram JSON file.")
        except Exception as error:
            print("ERROR:", str(error))
            return render_template("upload.html", message="Something went wrong while analyzing your ZIP file.")

    return render_template("upload.html")

if __name__ == "__main__":
    app.run(debug=True)






