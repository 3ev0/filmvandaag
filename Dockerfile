FROM python:3.10-slim

RUN apt-get update && apt-get install -y wget gnupg curl

ENV PYTHONUNBUFFERED True
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY ./src ./src/
COPY ./requirements.txt requirements.txt

RUN pip install --upgrade pip
# Install python package dependencies.
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python3", "src/filmvandaag.py"]
