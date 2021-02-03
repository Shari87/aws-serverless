import csv
import json
import os
import boto3
import datetime as dt

queue_url = 'QUEUE_NAME'

s3 = boto3.client('s3')
sqs = boto3.client('sqs')

def lambda_handler(event, context):

    datestamp = dt.datetime.now().strftime("%Y/%m/%d")
    filename_csv = "/tmp/file_{ds}.csv".format(ds=datestamp)
    filename_json = "/tmp/file_{ds}.json".format(ds=datestamp)

    # create an empty list
    json_data = []

    for record in event['Records']:
        bucket_name = record['s3']['bucket']['name']
        key_name = record['s3']['object']['key']

    s3_object = s3.get_object(Bucket=bucket_name, key=key_name)
    data = s3_object['Body'].read()
    contents = data.decode('utf-8')

    with open(filename_csv,'a') as csv_data:
        csv_data.write(contents)
    
    with open(filename_csv) as csv_data:
        csv_reader = csv.DictReader(csv_data)
        for csv_row in csv_reader:
            json_data.append(csv_row)

     with open(filename_json, 'w') as json_file:
        json_file.write(json.dumps(json_data, indent=4))

    
    with open(filename_json, 'r') as json_file_contents:
        response = sqs.send_message(QueueUrl=queue_url,MessageBody=json_file_contents.write())
