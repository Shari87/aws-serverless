# AWS-Serverless-Project
# Objective
To design a data processing pipeline taking input in CSV format from a user and to produce output in JSON format for internal processing
# Project Architecture
![aws-serverless](https://user-images.githubusercontent.com/49628483/106571707-7f7a0880-655d-11eb-9c2b-54df9fa88249.JPG)
# Services Used
* Amazon Simple Storage Service (S3)
* Amazon Simple Notification Service (SNS)
* Amazon Lambda
* Amazon Simple Queue Service (SQS)
# Architecture Overview
* When a user uploads the CSV files to the configured S3 bucket, an S3 event notification will fire towards SNS, publishing the event inside the respective topic
* The subscriber for this topic would be a Lambda function
* The Lambda function parses the event and sends a message to the message queue; in this context the SQS
* Due to the decoupling of publishing and subscribing with SNS we are free to add more consumers for the events later
# Detailed Description of Services
* S3 organizes the objects in buckets.Within a bucket you can reference individual objects by key
* Uploading the CSV's to S3 can either be done via the AWS console, the AWS CLI, or directly through the S3 API
* Assuming that the partner is going to use the CLI for uploading. Both the management console as well as the CLI work pretty smoothly, as they handle all the low level communication with S3
* S3 allows to configure **event notifications**. Events can be created based on object creation or deletion(in this context; as soon as an upload of a CSV is made, an object is created) as well as notification of object loss for objects with reduced redundancy.
* We can choose to either send the event to an SNS topic, an SQS queue or a lambda function.
* In this context, we are going to send the events to SNS and then allow interested applications to subscribe. This is referred to as the **messaging fanout pattern**. Instead of sending events directly all the parties, by using SNS as an intermediate broker we can de-couple publishing and susbcription
* SNS is a simple pub/sub service which organizes around topics. A topic groups together messages of the same type which might be of interest to a set of subscribers. In case of a new message being published to a topic, SNS will notify all subscribers
* SNS also facilitates delivery policies which includes configuration of maximum receive rates and retry delays
* Since the goal is to send the JSON message to the message queue. We can achieve that by subscribing a Lambda function to the SNS topic
* On invocation, the Lambda function will parse and inspect the event notification, process the CSV file which is uploaded into S3, and forward the output to a message queue, which is SQS
* SQS can be used to store the output (the generated JSON) from the Lambda function and this further can be processed asynchronously using another Lambda function or a long running polling service
# Implementation
* To develop the solution, I'd be using the following tools and language:
    * Terraform
    * Python 3.7
    * VS Code + Terraform Plugin
## S3 Bucket
* Firstly, let's create the S3 bucket which can be utilized by the partner to upload the CSV files
* We need to provide a bucket name and an ACL
* The ACL will be ``public-read`` as we want to enable people to make their CSV's publicy readable but require authentication for uploads
* The ``force-destroy`` option allows Terraform to destroy the bucket even if it is not empty
```
variable "aws_s3_bucket_upload_name" {
  default = "sns-sqs-upload-bucket"
}

resource "aws_s3_bucket" "upload" {
  bucket = "${var.aws_s3_bucket_upload_name}"
  acl    = "public-read"
  force_destroy = true
}
```
## SNS Topic
* Next, let's create the SNS topic