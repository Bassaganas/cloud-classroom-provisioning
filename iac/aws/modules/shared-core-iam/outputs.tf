output "github_actions_role_arn" {
  description = "IAM role ARN for the shared-core GitHub Actions deploy workflow"
  value       = aws_iam_role.shared_core_github_actions.arn
}
