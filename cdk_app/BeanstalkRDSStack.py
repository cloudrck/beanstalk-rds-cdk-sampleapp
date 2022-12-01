from aws_cdk import (
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_s3_assets as s3assets,
    aws_elasticbeanstalk as eb,
    aws_secretsmanager as sm,
    aws_iam as iam,
    Stack, CfnOutput
)

import json, os
from constructs import Construct

class BeanstalkRDSStack(Stack):

    def __init__(self, scope: Construct, id: str, props, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Database user
        db_master_username = {
            "db-master-username": props['db_master_username']
        }
        # create new secret in SecretsManager
        secret = sm.Secret(self,
                            "db-user-password-secret",
                            description="db master user password",
                            secret_name="db-master-user-password",
                            generate_secret_string=sm.SecretStringGenerator(
                                exclude_punctuation=True,
                                exclude_characters="\\/@\"",
                                secret_string_template=json.dumps(db_master_username),
                                generate_string_key="db-master-user-password"
                            )
        )
        # create db instance
        # Retrieve password and pass to the Db Instance (https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk/SecretValue.html#aws_cdk.SecretValue.unsafe_unwrap)
        db_inst = rds.CfnDBInstance(
            self,
            "rds-instance",
            engine=props['db_instance_engine'],
            db_subnet_group_name=props['db_subnet_group_name'],
            db_instance_identifier=props['db_instance_identifier'],
            db_instance_class="db.t2.micro",
            deletion_protection=False,
            multi_az=False,
            vpc_security_groups=[props['private_db_sg_id']],
            allocated_storage="20",
            master_username=props['db_master_username'],
            master_user_password=secret.secret_value_from_json("db-master-user-password").unsafe_unwrap(),
            db_name=props['db_name']
        )

        # On Unix, get path to current directory to use relative path to zip file
        dir_path = os.path.dirname(os.path.realpath(__file__))
        appName = props['eb_name']

        # Move zip file to S3 bucket created by CDK so Beanstalk can pull from.
        webAppZipArchive = s3assets.Asset(self, 'WebAppZip',
            path=dir_path+"/../../aws_onboarding.zip"
            )

        # Elastic Beanstalk application object
        eb_app = eb.CfnApplication(self, 'MyApplication',
                                   application_name = appName,
        )

        # Beanstalk application version object. The actual Beanstalk deployment
        appVersionProps = eb.CfnApplicationVersion(self, 'MyAppVersion',
            application_name = appName,
            source_bundle = eb.CfnApplicationVersion.SourceBundleProperty(
            s3_bucket=webAppZipArchive.s3_bucket_name,
            s3_key=webAppZipArchive.s3_object_key
            )
        )

        # Attach the application version to the application object.
        appVersionProps.add_depends_on(eb_app)

        # Create a role
        myRole = iam.Role(self, f"{appName}-aws-elasticbeanstalk-ec2-role",
            assumed_by= iam.ServicePrincipal('ec2.amazonaws.com')
            )

        # Grab managed policy as an object
        managedPolicy = iam.ManagedPolicy.from_aws_managed_policy_name('AWSElasticBeanstalkWebTier')

        # Attach managed policy to my Role.
        myRole.add_managed_policy(managedPolicy)

        my_profile_name = f"{appName}-InstanceProfile"

        instanceProfile = iam.CfnInstanceProfile(self, my_profile_name,
            roles=[myRole.role_name],
            instance_profile_name=my_profile_name
            )

        # Set a bunch of Beanstalk options. Most of these props[] are referenced from reseources created in the NetworkStack
        eb_option_settings = [eb.CfnEnvironment.OptionSettingProperty(
            namespace='aws:autoscaling:launchconfiguration',
            option_name='IamInstanceProfile',
            value=my_profile_name
            ),
            eb.CfnEnvironment.OptionSettingProperty(
                namespace='aws:autoscaling:asg',
                option_name='MinSize',
                value='1'
                ),
            eb.CfnEnvironment.OptionSettingProperty(
                namespace='aws:autoscaling:asg',
                option_name='MaxSize',
                value='1'
                ),
            eb.CfnEnvironment.OptionSettingProperty(
                namespace='aws:ec2:instances',
                option_name='InstanceTypes',
                value='t2.micro'
                ),
             eb.CfnEnvironment.OptionSettingProperty(
                namespace='aws:ec2:vpc',
                option_name='VPCId',
                value=props['vpc-id']
                ),
            eb.CfnEnvironment.OptionSettingProperty(
                namespace='aws:ec2:vpc',
                option_name='Subnets',
                value=f"{props['public_subnet_id_1']}, {props['public_subnet_id_2']}"
                ),
            eb.CfnEnvironment.OptionSettingProperty(
                namespace='aws:ec2:vpc',
                option_name='ELBSubnets',
                value=f"{props['public_subnet_id_1']}, {props['public_subnet_id_2']}"
                ),
            eb.CfnEnvironment.OptionSettingProperty(
                namespace='aws:autoscaling:launchconfiguration',
                option_name='SecurityGroups',
                value=props['webserver_sg_id']
                ),
            eb.CfnEnvironment.OptionSettingProperty(
                namespace='aws:elasticbeanstalk:environment',
                option_name='LoadBalancerType',
                value='application'
                )
                              ]

        elvEnv = eb.CfnEnvironment(self, 'Environment',
            application_name=appName,
            solution_stack_name=props['beanstalk_stack'],
            option_settings=eb_option_settings,
            version_label=appVersionProps.ref
            )
