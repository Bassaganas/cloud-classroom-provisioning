terraform {
  backend "s3" {
    bucket         = "terraform-state-classroom-shared"
    key            = "classroom/shared/terraform.tfstate"
    region         = "eu-west-3"
    dynamodb_table = "terraform-locks-classroom-shared"
    encrypt        = true
  }
}
