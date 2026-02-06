terraform {
  backend "s3" {
    # TODO: Update to your Fellowship backend bucket name
    bucket         = "terraform-state-fellowship-of-the-build"
    key            = "classroom/fellowship/terraform.tfstate"
    region         = "eu-west-3"
    dynamodb_table = "terraform-locks-fellowship"
    encrypt        = true
  }
}
