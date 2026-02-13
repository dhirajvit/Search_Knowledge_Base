resource "aws_vpc" "main" {
  provider             = aws.ap-southeast-2
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-vpc"
    Environment = var.environment
  }
}

resource "aws_subnet" "public" {
  provider                = aws.ap-southeast-2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "ap-southeast-2a"

  tags = {
    Name        = "${var.project_name}-${var.environment}-public-subnet"
    Environment = var.environment
  }
}

resource "aws_subnet" "private" {
  provider          = aws.ap-southeast-2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "ap-southeast-2a"

  tags = {
    Name        = "${var.project_name}-${var.environment}-private-subnet"
    Environment = var.environment
  }
}

resource "aws_internet_gateway" "main" {
  provider = aws.ap-southeast-2
  vpc_id   = aws_vpc.main.id

  tags = {
    Name        = "${var.project_name}-${var.environment}-igw"
    Environment = var.environment
  }
}

resource "aws_route_table" "public_route_table" {
  provider = aws.ap-southeast-2
  vpc_id   = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-public-rt"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "public" {
  provider       = aws.ap-southeast-2
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public_route_table.id
}

resource "aws_route_table" "private" {
  provider = aws.ap-southeast-2
  vpc_id   = aws_vpc.main.id

  tags = {
    Name        = "${var.project_name}-${var.environment}-private-rt"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "private" {
  provider       = aws.ap-southeast-2
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
}
