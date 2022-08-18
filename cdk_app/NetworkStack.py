from aws_cdk import (
    aws_ec2 as ec2,
    aws_rds as rds,
    Stack, CfnOutput, CfnTag
)

from constructs import Construct

class NetworkStack(Stack):

    def __init__(self, scope: Construct, id: str, props, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create VPC

        vpc = ec2.CfnVPC(
            self,
            "tutorial-vpc",
            enable_dns_hostnames=True,
            enable_dns_support=True,
            cidr_block="10.0.0.0/16"

        )
        self.vpc = vpc

        vpc.tags.set_tag(key="Name",value=props['vpc_name'])

                
        # Create Routing table for private subnet
        route_table_private = ec2.CfnRouteTable(
            self,
            "rtb-private",
            vpc_id=vpc.ref
        )

        route_table_private.tags.set_tag(key="Name",value="EB Private Routing Table")


        # Create Routing table for public subnet
        route_table_public = ec2.CfnRouteTable(
            self,
            "rtb-public",
            vpc_id=vpc.ref
        )

        route_table_public.tags.set_tag(key="Name",value="EB Public Routing Table")


        # Create public subnet
        public_subnet_1 = ec2.CfnSubnet(
            self,
            "public_subnet_1",
            cidr_block="10.0.0.0/24",
            vpc_id=vpc.ref,
            map_public_ip_on_launch=True,
            availability_zone=f"{props['region']}a" # us-east-1a
        )

        public_subnet_2 = ec2.CfnSubnet(
            self,
            "public_subnet_2",
            cidr_block="10.0.3.0/24",
            vpc_id=vpc.ref,
            map_public_ip_on_launch=True,
            availability_zone=f"{props['region']}b"
        )
        # Create Elastic ip
        eip = ec2.CfnEIP(
            self,
            "elastic_ip",
        )

        # Create internet gateway
        inet_gateway = ec2.CfnInternetGateway(
            self,
            "eb-igw",
            tags=[CfnTag(key="Name",value="eb-igw")]
        )

        # Attach internet gateway to vpc
        ec2.CfnVPCGatewayAttachment(
            self,
            "igw-attachment",
            vpc_id=vpc.ref,
            internet_gateway_id=inet_gateway.ref
        )

        # Create NAT gateway, attach elastic-ip, public subnet
        nat_gateway = ec2.CfnNatGateway(
            self,
            "natgateway",
            allocation_id=eip.attr_allocation_id,
            subnet_id=public_subnet_1.ref,

        )

        # Create private subnet 1
        private_subnet_1 = ec2.CfnSubnet(
            self,
            "private-subnet1",
            cidr_block="10.0.1.0/24",
            vpc_id=vpc.ref,
            availability_zone=f"{props['region']}b"
        )

        # Create private subnet 2
        private_subnet_2 = ec2.CfnSubnet(
            self,
            "private-subnet2",
            cidr_block="10.0.2.0/24",
            vpc_id=vpc.ref,
            availability_zone=f"{props['region']}c"
        )

        public_subnet_1.tags.set_tag(key="Name",value="subnet-eb-public-1")
        public_subnet_2.tags.set_tag(key="Name",value="subnet-eb-public-2")
        private_subnet_1.tags.set_tag(key="Name",value="subnet-eb-private-1")
        private_subnet_2.tags.set_tag(key="Name",value="subnet-eb-private-2")

        # Associate private subnet with the created routing table
        ec2.CfnSubnetRouteTableAssociation(
                self,
                "rtb-assoc-priv001",
                route_table_id=route_table_private.ref,
                subnet_id=private_subnet_1.ref
        )

        ec2.CfnSubnetRouteTableAssociation(
                self,
                "rtb-assoc-priv002",
                route_table_id=route_table_private.ref,
                subnet_id=private_subnet_2.ref
        )

        ec2.CfnSubnetRouteTableAssociation(
            self,
            "rtb-assoc-public001",
            route_table_id=route_table_public.ref,
            subnet_id=public_subnet_1.ref
        )
        ec2.CfnSubnetRouteTableAssociation(
            self,
            "rtb-assoc-public002",
            route_table_id=route_table_public.ref,
            subnet_id=public_subnet_2.ref
        )

        # Create a new public route to use the internet gateway
        ec2.CfnRoute(
            self,
            "public-route",
            route_table_id=route_table_public.ref,
            gateway_id=inet_gateway.ref,
            destination_cidr_block="0.0.0.0/0",
        
        )

        # Create security groups

        # public web server

        webserver_sec_group = ec2.CfnSecurityGroup(
            self,
            "webserver-sec-group",
            group_description="webserver security group",
            vpc_id=vpc.ref,
            
        )

        # Restrict SSH port access to only yourself
        ssh_ingress = ec2.CfnSecurityGroupIngress(
            self,
            "sec-group-ssh-ingress",
            ip_protocol="tcp",
            cidr_ip=props['wan_ip']+"/32",
            from_port=22,
            to_port=22,
            group_id=webserver_sec_group.ref
        )

        # Allow http to internet
        http_ingress = ec2.CfnSecurityGroupIngress(
            self,
            "sec-group-http-ingress",
            ip_protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_ip="0.0.0.0/0",
            group_id=webserver_sec_group.ref
        )

        webserver_sec_group.tags.set_tag(key="Name",value="sg-eb-webserver")

        
        # Create security group for the EB instance
        db_sec_group = ec2.CfnSecurityGroup(
            self,
            "dbserver-sec-group",
            group_description="DB Instance Security Group",
            vpc_id=vpc.ref
        )

        db_sec_group.tags.set_tag(key="Name",value="sg-eb-db")

        # Allow port 3306 only to the webserver in order to access MySQL
        db_ingress = ec2.CfnSecurityGroupIngress(
            self,
            "sec-group-db-ingress",
            ip_protocol="tcp",
            from_port=3306,
            to_port=3306,
            group_id=db_sec_group.ref,
            source_security_group_id=webserver_sec_group.ref
        )

        self.output_props = props.copy()
        self.output_props['webserver_sg_id'] = webserver_sec_group.ref
        self.output_props['public_subnet_id_1'] =  public_subnet_1.ref
        self.output_props['public_subnet_id_2'] =  public_subnet_2.ref
        self.output_props['private_db_sg_id'] = db_sec_group.ref
        self.output_props['vpc-id'] = vpc.ref

        # Create EB subnet group
        rds.CfnDBSubnetGroup(
            self,
            "rds_db_subnet_group",
            db_subnet_group_description="EB DB Subnet Group",
            db_subnet_group_name=props['db_subnet_group_name'],
            subnet_ids=[private_subnet_1.ref,private_subnet_2.ref],
        )

        CfnOutput(
            self,
            "output-db-sg-id",
            value=self.output_props['private_db_sg_id']
        )
        CfnOutput(
            self,
            "output-vpc-id",
            value=self.output_props['vpc-id']
        )



    @property
    def outputs(self):
        return self.output_props
