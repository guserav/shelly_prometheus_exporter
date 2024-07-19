FROM python:3.12

COPY requirenments.txt requirenments.txt

RUN pip install -r requirenments.txt

COPY shelly_exporter.py shelly_exporter.py

EXPOSE 8000

CMD ["python3", "shelly_exporter.py"]
