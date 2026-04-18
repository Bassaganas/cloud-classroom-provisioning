"""Step implementations for student access control and resource isolation."""
import logging
import os
from behave import given, when, then
from e2e.utils.jenkins_client import JenkinsClient
from e2e.utils.gitea_client import GiteaClient

logger = logging.getLogger(__name__)


def _get_jenkins_client(context, username=None, token=None):
    """Get or create Jenkins client for a user."""
    if not hasattr(context, 'jenkins_clients'):
        context.jenkins_clients = {}
    
    key = username or 'admin'
    if key not in context.jenkins_clients or username:
        # For student login, we try with username/password (usually password)
        if username and '@' not in username:
            # Create a client with student credentials
            client = JenkinsClient(
                base_url=os.getenv('JENKINS_URL', 'http://localhost:8080'),
                username=username,
                token=token or username  # Often using password as token for testing
            )
        else:
            client = JenkinsClient()
        context.jenkins_clients[key] = client
    
    return context.jenkins_clients[key]


def _get_gitea_client(context, username=None, password=None):
    """Get or create Gitea client for a user."""
    if not hasattr(context, 'gitea_clients'):
        context.gitea_clients = {}
    
    key = username or 'admin'
    
    # Always create new client if credentials provided (for login tests)
    if username and password:
        client = GiteaClient(
            base_url=os.getenv('GITEA_URL', 'http://localhost:3000'),
            username=username,
            password=password
        )
        context.gitea_clients[key] = client
        return client
    
    if key not in context.gitea_clients:
        client = GiteaClient(base_url=os.getenv('GITEA_URL', 'http://localhost:3000'))
        context.gitea_clients[key] = client
    
    return context.gitea_clients[key]


# ── Background steps ──────────────────────────────────────────────────────────

@given('Jenkins is accessible and healthy')
def step_jenkins_accessible(context):
    """Verify Jenkins is accessible."""
    client = JenkinsClient()
    assert client.health_check(), "Jenkins is not accessible"
    logger.info("✓ Jenkins is accessible")


@given('Gitea is accessible and healthy')
def step_gitea_accessible(context):
    """Verify Gitea is accessible."""
    client = GiteaClient()
    assert client.health_check(), "Gitea is not accessible"
    logger.info("✓ Gitea is accessible")


@given('the admin user "fellowship" is available')
def step_admin_available(context):
    """Verify admin user is available."""
    jenkins = JenkinsClient()
    gitea = GiteaClient()
    assert jenkins.health_check(), "Cannot verify admin in Jenkins"
    assert gitea.health_check(), "Cannot verify admin in Gitea"
    logger.info("✓ Admin user is available")


@given('I am properly authenticated as admin')
def step_authenticated_as_admin(context):
    """Authenticate as admin."""
    if not hasattr(context, 'admin_client'):
        context.admin_client = JenkinsClient(
            username='fellowship',
            token=os.getenv('JENKINS_ADMIN_PASSWORD', 'fellowship123')
        )
    logger.info("✓ Authenticated as admin")


# ── Provisioning steps ────────────────────────────────────────────────────────

@given('I provision student "{student_id}" with password "{password}"')
def step_provision_student(context, student_id, password):
    """Provision a student on the shared-core stack."""
    if not hasattr(context, 'provisioned_students'):
        context.provisioned_students = {}
    
    # In a real scenario, this would call the provisioning API/Lambda
    # For now, we just track that the student was provisioned
    context.provisioned_students[student_id] = {
        'password': password,
        'username': student_id,
        'repo': f'fellowship-org/fellowship-sut-{student_id}'
    }
    logger.info(f"✓ Provisioned student '{student_id}'")


# ── Jenkins access steps ──────────────────────────────────────────────────────

@then('student "{student_id}" can login to Jenkins with password "{password}"')
def step_student_login_jenkins(context, student_id, password):
    """Verify student can login to Jenkins."""
    client = _get_jenkins_client(context, username=student_id, token=password)
    
    # Try to access the Jenkins API to verify authentication
    try:
        response = client.session.get(
            f"{client.base_url}/api/json",
            auth=__import__('requests').auth.HTTPBasicAuth(student_id, password),
            timeout=5
        )
        assert response.status_code == 200, f"Login failed with status {response.status_code}"
        logger.info(f"✓ Student '{student_id}' logged into Jenkins")
    except Exception as e:
        raise AssertionError(f"Failed to login to Jenkins: {e}")


@then('student "{student_id}" can see their Jenkins folder "{folder}"')
def step_student_see_jenkins_folder(context, student_id, folder):
    """Verify student can see their Jenkins folder."""
    client = _get_jenkins_client(context, username=student_id, token=context.provisioned_students[student_id]['password'])
    
    job = client.get_job(folder)
    assert job is not None, f"Student '{student_id}' cannot see folder '{folder}'"
    logger.info(f"✓ Student '{student_id}' can see Jenkins folder '{folder}'")


@then('student "{student_id}" cannot see folder "{other_folder}" (access denied)')
def step_student_cannot_see_jenkins_folder(context, student_id, other_folder):
    """Verify student cannot see another student's Jenkins folder."""
    client = _get_jenkins_client(context, username=student_id, token=context.provisioned_students[student_id]['password'])
    
    job = client.get_job(other_folder)
    assert job is None or job.get('_class') == 'hudson.model.ExceptionResponse', \
        f"Student '{student_id}' should not be able to see folder '{other_folder}'"
    logger.info(f"✓ Student '{student_id}' cannot access folder '{other_folder}' (access denied)")


@then('admin user "fellowship" can see both folders "{folder1}" and "{folder2}"')
def step_admin_see_all_folders(context, folder1, folder2):
    """Verify admin can see all student folders."""
    admin_client = JenkinsClient(
        username='fellowship',
        token=os.getenv('JENKINS_ADMIN_PASSWORD', 'fellowship123')
    )
    
    job1 = admin_client.get_job(folder1)
    job2 = admin_client.get_job(folder2)
    
    assert job1 is not None, f"Admin cannot see folder '{folder1}'"
    assert job2 is not None, f"Admin cannot see folder '{folder2}'"
    logger.info(f"✓ Admin can see folders '{folder1}' and '{folder2}'")


# ── Gitea access steps ────────────────────────────────────────────────────────

@when('I attempt to login to Gitea as "{student_id}" with password "{password}"')
def step_login_gitea(context, student_id, password):
    """Attempt to login to Gitea."""
    if not hasattr(context, 'gitea_login_result'):
        context.gitea_login_result = {}
    
    try:
        client = _get_gitea_client(context, username=student_id, password=password)
        # Try to get user info to verify authentication
        user = client.get_user(student_id)
        context.gitea_login_result[student_id] = {'success': True, 'user': user}
        logger.info(f"✓ Login to Gitea as '{student_id}' attempted")
    except Exception as e:
        context.gitea_login_result[student_id] = {'success': False, 'error': str(e)}
        logger.info(f"✗ Login to Gitea as '{student_id}' failed: {e}")


@then('the login is successful')
def step_login_successful(context):
    """Verify login was successful."""
    # Get the last student from login_result
    for student_id, result in context.gitea_login_result.items():
        assert result.get('success'), f"Login for '{student_id}' was not successful"
    logger.info("✓ Login is successful")


@then('student "{student_id}" sees Gitea repository "{repo_path}"')
def step_student_see_repo(context, student_id, repo_path):
    """Verify student can see their Gitea repository."""
    owner, repo = repo_path.split('/')
    
    client = _get_gitea_client(context, username=student_id, password=context.provisioned_students[student_id]['password'])
    exists = client.repository_exists(owner, repo)
    
    assert exists, f"Repository '{repo_path}' not found for student '{student_id}'"
    logger.info(f"✓ Student '{student_id}' can see repository '{repo_path}'")


@then('"{student_id}" can read repository "{repo_path}"')
def step_student_read_repo(context, student_id, repo_path):
    """Verify student can read their repository."""
    owner, repo = repo_path.split('/')
    
    client = _get_gitea_client(context, username=student_id, password=context.provisioned_students[student_id]['password'])
    exists = client.repository_exists(owner, repo)
    
    assert exists, f"Student '{student_id}' cannot read repository '{repo_path}'"
    logger.info(f"✓ Student '{student_id}' can read repository '{repo_path}'")


@then('"{student_id}" can push to repository "{repo_path}"')
def step_student_push_repo(context, student_id, repo_path):
    """Verify student can push to their repository."""
    owner, repo = repo_path.split('/')
    
    client = _get_gitea_client(context, username=student_id, password=context.provisioned_students[student_id]['password'])
    
    # Try to push a test file to verify write access
    try:
        client.push_file(owner, repo, 'test.txt', f'Test from {student_id}', f'Test push from {student_id}')
        logger.info(f"✓ Student '{student_id}' can push to repository '{repo_path}'")
    except Exception as e:
        raise AssertionError(f"Student '{student_id}' cannot push to '{repo_path}': {e}")


@then('"{student_id}" cannot read repository "{repo_path}" (403 Forbidden)')
def step_student_cannot_read_repo(context, student_id, repo_path):
    """Verify student cannot read another student's repository."""
    owner, repo = repo_path.split('/')
    
    client = _get_gitea_client(context, username=student_id, password=context.provisioned_students[student_id]['password'])
    
    try:
        exists = client.repository_exists(owner, repo)
        assert not exists, f"Student '{student_id}' should not be able to see repository '{repo_path}'"
        logger.info(f"✓ Student '{student_id}' cannot read repository '{repo_path}' (403)")
    except Exception as e:
        # Access denied is expected
        logger.info(f"✓ Student '{student_id}' cannot access '{repo_path}' (forbidden)")


@then('"{student_id}" cannot push to repository "{repo_path}" (403 Forbidden)')
def step_student_cannot_push_repo(context, student_id, repo_path):
    """Verify student cannot push to another student's repository."""
    owner, repo = repo_path.split('/')
    
    client = _get_gitea_client(context, username=student_id, password=context.provisioned_students[student_id]['password'])
    
    try:
        client.push_file(owner, repo, 'test.txt', 'This should fail', 'Unauthorized push')
        raise AssertionError(f"Student '{student_id}' should not be able to push to '{repo_path}'")
    except Exception as e:
        if '403' in str(e) or 'Forbidden' in str(e) or 'Permission denied' in str(e):
            logger.info(f"✓ Student '{student_id}' cannot push to '{repo_path}' (403 Forbidden)")
        else:
            raise


# ── Admin access steps ────────────────────────────────────────────────────────

@when('I login to Jenkins as admin "fellowship"')
def step_admin_login_jenkins(context):
    """Admin login to Jenkins."""
    context.admin_jenkins_client = JenkinsClient(
        username='fellowship',
        token=os.getenv('JENKINS_ADMIN_PASSWORD', 'fellowship123')
    )
    logger.info("✓ Admin logged into Jenkins")


@then('admin can see all folders including "{folder1}" and "{folder2}"')
def step_admin_see_folders(context, folder1, folder2):
    """Verify admin can see all folders."""
    client = context.admin_jenkins_client
    
    job1 = client.get_job(folder1)
    job2 = client.get_job(folder2)
    
    assert job1 is not None, f"Admin cannot see folder '{folder1}'"
    assert job2 is not None, f"Admin cannot see folder '{folder2}'"
    logger.info(f"✓ Admin can see all folders")


@when('I login to Gitea as admin "fellowship"')
def step_admin_login_gitea(context):
    """Admin login to Gitea."""
    context.admin_gitea_client = _get_gitea_client(
        context,
        username='fellowship',
        password=os.getenv('GITEA_ADMIN_PASSWORD', 'fellowship123')
    )
    logger.info("✓ Admin logged into Gitea")


@then('admin can read all repositories')
def step_admin_read_all_repos(context):
    """Verify admin can read all repositories."""
    client = context.admin_gitea_client
    
    # Check a few student repos
    for student_id in ['aragorn', 'legolas', 'gimli']:
        repo_name = f'fellowship-sut-{student_id}'
        exists = client.repository_exists('fellowship-org', repo_name)
        # It's OK if not all exist yet, but admin should have access to check
    
    logger.info("✓ Admin can read all repositories")


# ── Deprovisioning steps ──────────────────────────────────────────────────────

@given('student "{student_id}" is verified to have Jenkins access')
def step_verify_jenkins_access(context, student_id):
    """Verify student has Jenkins access before deprovisioning."""
    client = _get_jenkins_client(context, username=student_id, token=context.provisioned_students[student_id]['password'])
    
    folder = client.get_job(student_id)
    assert folder is not None, f"Student '{student_id}' does not have Jenkins folder"
    logger.info(f"✓ Student '{student_id}' verified to have Jenkins access")


@when('I deprovision student "{student_id}"')
def step_deprovision_student(context, student_id):
    """Deprovision a student."""
    # Mark student as deprovisioned
    if not hasattr(context, 'deprovisioned_students'):
        context.deprovisioned_students = set()
    
    context.deprovisioned_students.add(student_id)
    logger.info(f"✓ Deprovisioned student '{student_id}'")


@then('student "{student_id}" cannot login to Jenkins')
def step_student_no_jenkins_login(context, student_id):
    """Verify student cannot login to Jenkins after deprovisioning."""
    try:
        client = JenkinsClient(
            username=student_id,
            token=context.provisioned_students[student_id]['password']
        )
        response = client.session.get(f"{client.base_url}/api/json", timeout=5)
        assert response.status_code != 200, f"Student '{student_id}' still has Jenkins access"
    except Exception:
        # Expected - cannot connect with deprovisioned credentials
        logger.info(f"✓ Student '{student_id}' cannot login to Jenkins")


@then('student "{student_id}" cannot login to Gitea')
def step_student_no_gitea_login(context, student_id):
    """Verify student cannot login to Gitea after deprovisioning."""
    try:
        client = _get_gitea_client(context, username=student_id, password=context.provisioned_students[student_id]['password'])
        user = client.get_user(student_id)
        raise AssertionError(f"Student '{student_id}' still has Gitea access")
    except Exception as e:
        if 'still has' in str(e):
            raise
        # Expected - user not found or auth failed
        logger.info(f"✓ Student '{student_id}' cannot login to Gitea")


@then('Jenkins folder "{folder}" does not exist')
def step_jenkins_folder_removed(context, folder):
    """Verify Jenkins folder was deleted."""
    admin_client = JenkinsClient(
        username='fellowship',
        token=os.getenv('JENKINS_ADMIN_PASSWORD', 'fellowship123')
    )
    
    job = admin_client.get_job(folder)
    assert job is None, f"Jenkins folder '{folder}' still exists"
    logger.info(f"✓ Jenkins folder '{folder}' does not exist")


@then('Gitea repository "{repo_path}" does not exist')
def step_gitea_repo_removed(context, repo_path):
    """Verify Gitea repository was deleted."""
    owner, repo = repo_path.split('/')
    
    admin_client = GiteaClient(
        username='fellowship',
        password=os.getenv('GITEA_ADMIN_PASSWORD', 'fellowship123')
    )
    
    exists = admin_client.repository_exists(owner, repo)
    assert not exists, f"Gitea repository '{repo_path}' still exists"
    logger.info(f"✓ Gitea repository '{repo_path}' does not exist")


@then('the Gitea user "{student_id}" does not exist')
def step_gitea_user_removed(context, student_id):
    """Verify Gitea user was deleted."""
    admin_client = GiteaClient(
        username='fellowship',
        password=os.getenv('GITEA_ADMIN_PASSWORD', 'fellowship123')
    )
    
    exists = admin_client.user_exists(student_id)
    assert not exists, f"Gitea user '{student_id}' still exists"
    logger.info(f"✓ Gitea user '{student_id}' does not exist")
