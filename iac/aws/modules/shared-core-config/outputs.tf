output "config_parameter_names" {
  description = "SSM parameter names used by the shared-core deploy workflow"
  value = {
    instance_id                   = aws_ssm_parameter.shared_core_instance_id.name
    ssh_host                      = aws_ssm_parameter.shared_core_ssh_host.name
    jenkins_domain                = try(aws_ssm_parameter.shared_core_jenkins_domain[0].name, null)
    gitea_domain                  = try(aws_ssm_parameter.shared_core_gitea_domain[0].name, null)
    security_group_id             = aws_ssm_parameter.shared_core_security_group_id.name
    hosted_zone_id                = try(aws_ssm_parameter.shared_core_hosted_zone_id[0].name, null)
    gitea_admin_user              = aws_ssm_parameter.shared_core_gitea_admin_user.name
    gitea_admin_email             = aws_ssm_parameter.shared_core_gitea_admin_email.name
    gitea_org_name                = aws_ssm_parameter.shared_core_gitea_org_name.name
    agent_ecs_cluster_arn         = aws_ssm_parameter.jenkins_agent_ecs_cluster_arn.name
    agent_ecr_image               = aws_ssm_parameter.jenkins_agent_ecr_image.name
    agent_security_group_id       = aws_ssm_parameter.jenkins_agent_ecs_security_group_id.name
    agent_task_execution_role_arn = aws_ssm_parameter.jenkins_agent_task_execution_role_arn.name
    agent_task_role_arn           = aws_ssm_parameter.jenkins_agent_task_role_arn.name
    agent_subnet_id               = aws_ssm_parameter.jenkins_agent_subnet_id.name
  }
}
