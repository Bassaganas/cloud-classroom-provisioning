output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster used for Jenkins Fargate agents"
  value       = aws_ecs_cluster.jenkins_agents.arn
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.jenkins_agents.name
}

output "ecr_repository_url" {
  description = "ECR repository URL for the custom Jenkins agent image"
  value       = aws_ecr_repository.jenkins_agent.repository_url
}

output "agent_security_group_id" {
  description = "Security group ID for ECS Jenkins agent tasks"
  value       = aws_security_group.jenkins_agent.id
}

output "task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.task_execution.arn
}

output "task_role_arn" {
  description = "ARN of the ECS task role (runtime permissions for agent containers)"
  value       = aws_iam_role.task_role.arn
}

output "cloudwatch_log_group_name" {
  description = "CloudWatch log group name for agent logs"
  value       = aws_cloudwatch_log_group.jenkins_agents.name
}
