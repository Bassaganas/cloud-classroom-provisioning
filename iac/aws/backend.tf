terraform {
  backend "s3" {
    bucket         = "terraform-state-classroom-shared-euwest1"
    key            = "classroom/staging/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-locks-classroom-shared"
    encrypt        = true
  }
}
