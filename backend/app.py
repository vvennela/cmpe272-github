#python imports
from flask import Flask, jsonify
import os
from dotenv import load_dotenv

#file imports
from backend.database import db, DB_URL


#get env variables
load_dotenv()

app = Flask(
    __name__
)


app.config.from_mapping(
    SQLALCHEMY_DATABASE_URI=DB_URL,
    SECRET_KEY=os.getenv('SECRET_KEY')
)

#health check route
@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200

#connect db to app
db.init_app(app)

#register blue prints
#bp 1

#bp 2
#.....



#start the app
if __name__ == "__main__":
    #test database connection
    with app.app_context():
        try:
            with db.engine.connect():
                print("Connected to database")
        except Exception:
            print("Database connection failed")


    #run the app
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=True,
    )


