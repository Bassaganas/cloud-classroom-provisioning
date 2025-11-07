terraform {
  backend "s3" {
    bucket         = "terraform-state-testus-patronus-1760773678"
    key            = "classroom/testus-patronus/terraform.tfstate"
    region         = "eu-west-3"
    dynamodb_table = "terraform-locks-testus-patronus"
    encrypt        = true
  }
}
