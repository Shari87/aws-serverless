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
    * AWS CLI and AWS account 
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
* Next, let's create the SNS topic. To create an SNS topic we only need to provide a name
```
resource "aws_sns_topic" "upload" {
  name = "sns-sqs-upload-topic"
}
```
* The topic alone is not going to be useful if we do not allow anyone to publish messages
* In order to do that we attach a policy to the topic which allows our bucket resource to perform the ```SNS-Publish``` action on the topic
```
resource "aws_sns_topic_policy" "upload" {
  arn = "${aws_sns_topic.upload.arn}"

  policy = "${data.aws_iam_policy_document.sns_upload.json}"
}

data "aws_iam_policy_document" "sns_upload" {
  policy_id = "snssqssns"
  statement {
    actions = [
      "SNS:Publish",
    ]
    condition {
      test = "ArnLike"
      variable = "aws:SourceArn"

      values = [
        "arn:aws:s3:::${var.aws_s3_bucket_upload_name}",
      ]
    }
    effect = "Allow"
    principals {
      type = "AWS"
      identifiers = [
        "*"]
    }
    resources = [
      "${aws_sns_topic.upload.arn}",
    ]
    sid = "snssqssnss3upload"
  }
}
```
## S3 Event Notification
* With our SNS topic and S3 bucket resource defined we can combine them by creating an S3 bucket notification which will publish to the topic
* We can control the **events** we want to be notified about
* In this context, we are interested in all object creation events. An optional filter can be provided, for e.g., only notifications for ```*.csv``` in this case
```
resource "aws_s3_bucket_notification" "upload" {
  bucket = "${aws_s3_bucket.upload.id}"

  topic {
    topic_arn     = "${aws_sns_topic.upload.arn}"
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".csv"
  }
}
```
## Lambda Function
### Message Format
* We can use the webhook URL to create our Lambda function
* The function will receive S3 notifications wrapped inside SNS notifications
* Both are sent in JSON format, but the S3 notification is stored in the ```.Records.SNS.Message```field as a JSON string and has to be parsed as well
* This is an example of an SNS notification wrapper message
```
{
    "Records": [
        {
            "EventSource": "aws:sns",
            "EventVersion": "1.0",
            "EventSubscriptionArn": "arn:aws:sns:eu-central-1:195499643157:sns-sqs-upload-topic:c7173bbb-8dda-47f6-9f54-a6aa81f65aac",
            "Sns": {
                "Type": "Notification",
                "MessageId": "10a7c00e-af4b-5d93-9459-93a0604d93f5",
                "TopicArn": "arn:aws:sns:eu-central-1:195499643157:sns-sqs-upload-topic",
                "Subject": "Amazon S3 Notification",
                "Message": "<inner_message>",
                "Timestamp": "2018-06-28T11:55:50.578Z",
                "SignatureVersion": "1",
                "Signature": "sTuBzzioojbez0zGFzdk1DLiCmeby0VuSdBvg0yS6xU+dKOk3U8iFUzbS1ZaNI6oZp+LHhehDziaMkTHQ7qcLBebu9uTI++mGcEhlgz+Ns0Dx3mKXyMTZwEcNtwfHEblJPjHXRsuCQ36RuZjByfI0pc0rsISxdJDr9WElen4U0ltmbzUJVpB22x3ELqciEDRipcpVjZo+V2J8GjdCvKu4uFV6RW3cKDOb91jcPc1vUnv/L6Q1gARIUFTbeUYvLbbIAmOe5PiAT2ZYaAmzHKvGOep/RT+OZOA4F6Ro7pjY0ysFpvvaAp8QKp4Ikj40N9lVKtk24pW+/7OsQMUBGOGoQ==",
                "SigningCertUrl": "https://sns.eu-central-1.amazonaws.com/SimpleNotificationService-ac565b8b1a6c5d002d285f9598aa1d9b.pem",
                "UnsubscribeUrl": "https://sns.eu-central-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:eu-central-1:195499643157:sns-sqs-upload-topic:c7173bbb-8dda-47f6-9f54-a6aa81f65aac",
                "MessageAttributes": {}
            }
        }
    ]
}
```
* Inside the ```<inner_message>``` part you will find the actual S3 notification, which might look like this
```
{
    "Records": [
        {
            "eventVersion": "2.0",
            "eventSource": "aws:s3",
            "awsRegion": "eu-central-1",
            "eventTime": "2018-06-28T11:55:50.528Z",
            "eventName": "ObjectCreated:Put",
            "userIdentity": {
                "principalId": "AWS:AIDAI3EXAMPLEEXAMP"
            },
            "requestParameters": {
                "sourceIPAddress": "xxx.yyy.zzz.qqq"
            },
            "responseElements": {
                "x-amz-request-id": "0A8A0DA78EF73966",
                "x-amz-id-2": "/SD3sDpP1mcDc6pC61573e4DAFSCnYoesZxeETb4MV3PpVgT4ud8sw0dMrnWI9whB3RYhwGo+8A="
            },
            "s3": {
                "s3SchemaVersion": "1.0",
                "configurationId": "TriggerLambdaToConvertCsvToJson",
                "bucket": {
                    "name": "sns-lambda-upload-bucket",
                    "ownerIdentity": {
                        "principalId": "A2OMJ1OL5PYOLU"
                    },
                    "arn": "arn:aws:s3:::sns-sqs-upload-bucket"
                },
                "object": {
                    "key": "upload/input/clients.csv",
                    "size": 0,
                    "eTag": "x",
                    "sequencer": "x"
                }
            }
        }
    ]
}
```
## Source Code
* Let's head back to Lambda and write some code that will read the CSV when it arrives onto S3, process the file, convert to JSON, and then write as a json file to SQS
* [Lambda.py](lambda.py) is a simple Python file which basically describes the process mentioned in the above point
* Once this python file is created, zip the file up using the command
```bash
zip lambda lambda.py
```
* Before we can create the Lambda function we have to create an IAM role for the execution.
* Then we can create the Lambda function itself and also setup the permissions for the SNS notification to be able to invoke our Lambda function
* First the IAM role:
```
resource "aws_iam_role" "lambda_exec_role" {
  name        = "lambda_exec"
  path        = "/"
  description = "Allows Lambda Function to call AWS services on your behalf."

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
}
```
* Now we can define the Lambda function resource. It is useful also to specify the ```source_code_hash``` in order to trigger updates if the file has changed although the name did not
```
resource "aws_lambda_function" "lambda_function" {
  role             = "${aws_iam_role.lambda_exec_role.arn}"
  handler          = "${var.handler}"
  runtime          = "${var.runtime}"
  filename         = "lambda.zip"
  function_name    = "${var.function_name}"
  source_code_hash = "${base64sha256(file("lambda.zip"))}"
}
```
* Finally we have to create a permission which allows SNS messages to trigger the Lambda function
```
resource "aws_lambda_permission" "sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.lambda_function.function_name}"
  principal     = "sns.amazonaws.com"
  source_arn = "${aws_sns_topic.upload.arn}"
}
```
## Lambda Subscription
* The only link that is missing to complete our pipeline is the subscription of the Lambda function to the SNS topic
```
resource "aws_sns_topic_subscription" "lambda" {
  topic_arn = "${aws_sns_topic.upload.arn}"
  protocol  = "lambda"
  endpoint  = "${aws_lambda_function.lambda_function.arn}"
}
```
## SQS Queue
* The creation of the SQS queue works in a similar fashion
* We have to provide a name for the queue and a policy which allows SNS to send messages to the queue
```
resource "aws_sqs_queue" "upload" {
  name = "sns-sqs-upload"
}
```
```
resource "aws_sqs_queue_policy" "test" {
  queue_url = "${aws_sqs_queue.upload.id}"
  policy = "${data.aws_iam_policy_document.sqs_upload.json}"
}

data "aws_iam_policy_document" "sqs_upload" {
  policy_id = "__default_policy_ID"
  statement {
    actions = [
      "sqs:ReceiveMessage",
    ]
    condition {
      test = "ArnEquals"
      variable = "aws:SourceArn"

      values = [
        "${aws_lambda_function.lambda_function.arn}",
      ]
    }
    effect = "Allow"
    principals {
      type = "AWS"
      identifiers = [
        "*"]
    }
    resources = [
      "${aws_sqs_queue.upload.arn}",
    ]
    sid = "__default_statement_ID"
  }
}
```
## SQS Subscription
* Next we need to susbcribe the queue to the topic. SNS topic subscriptions
* SNS topic subscriptions support [multiple protocols](https://docs.aws.amazon.com/sns/latest/api/API_Subscribe.html):```http```,```https```,```email```