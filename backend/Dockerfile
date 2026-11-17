FROM python:3.13-slim 

WORKDIR /app

#install dependency
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

#copy files
COPY . .

#start app
CMD ["python", "-m", "backend.app"]