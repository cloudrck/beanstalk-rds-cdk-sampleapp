#!/usr/bin/env python3

import aws_cdk as core

from dotenv import dotenv_values
config = dotenv_values(".env")

from cdk_app.NetworkStack import NetworkStack
from cdk_app.BeanstalkRDSStack import BeanstalkRDSStack

# Important Environment settings. Note: Make sure to check most recent valid versions of `beanstalk_stack`
# https://awscli.amazonaws.com/v2/documentation/api/latest/reference/elasticbeanstalk/list-available-solution-stacks.html
props = {
            'namespace':'MyNamespace',
            'vpc_name':'vpc-myvpc',
            'instance_name':'rds-webserver',
            'instance_type':'t2.small',
            'wan_ip': config["WAN_IP"],
            'region': config["REGION"],
            'beanstalk_stack': '64bit Amazon Linux 2 v3.4.1 running Python 3.8',
            'eb_name':'myEbApp',
            'db_master_username': 'tutorial_user',
            'db_subnet_group_name': 'sgp-rds-db',
            'db_name': 'EBDb',
            'db_instance_identifier':'tutorial-db-instance',
            'db_instance_engine':'MYSQL'
        }


# For production accounts, AWS recommends explicitly environment account and region information
# https://docs.aws.amazon.com/cdk/v2/guide/environments.html
env = core.Environment(region=config["REGION"], account=config["ACCOUNT"])

app = core.App()
network_stack = NetworkStack(app, f"{props['namespace']}-network",props,env=env)

rds_stack = BeanstalkRDSStack(app, f"{props['namespace']}-db",network_stack.output_props, env=env)
rds_stack.add_dependency(network_stack)

app.synth()
