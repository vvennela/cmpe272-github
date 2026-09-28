import jenkins.model.Jenkins
import jenkins.model.GlobalConfiguration
import jenkins.model.JenkinsLocationConfiguration
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.model.FreeStyleProject
import hudson.tasks.Shell
import hudson.tasks.ArtifactArchiver
import hudson.plugins.git.GitSCM
import hudson.plugins.git.UserRemoteConfig
import hudson.plugins.git.BranchSpec
import hudson.tasks.LogRotator
import com.cloudbees.jenkins.GitHubPushTrigger
import com.cloudbees.plugins.credentials.SystemCredentialsProvider
import com.cloudbees.plugins.credentials.CredentialsScope
import com.cloudbees.plugins.credentials.domains.Domain
import org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl
import org.jenkinsci.plugins.github.config.GitHubPluginConfig
import org.jenkinsci.plugins.github.config.HookSecretConfig
import hudson.util.Secret

def jenkins = Jenkins.get()
def password = new File('/run/jenkins-secrets/admin-password').text.trim()
def webhookSecret = new File('/run/jenkins-secrets/webhook-secret').text.trim()
assert password && webhookSecret
if (!(jenkins.securityRealm instanceof HudsonPrivateSecurityRealm)) {
    def realm = new HudsonPrivateSecurityRealm(false)
    realm.createAccount('admin', password)
    jenkins.setSecurityRealm(realm)
}
def authorization = new FullControlOnceLoggedInAuthorizationStrategy()
authorization.setAllowAnonymousRead(false)
jenkins.setAuthorizationStrategy(authorization)
jenkins.setNumExecutors(1)
jenkins.setSlaveAgentPort(-1)
JenkinsLocationConfiguration.get().setUrl('http://localhost:8080/')

def store = SystemCredentialsProvider.getInstance().getStore()
def credential = new StringCredentialsImpl(CredentialsScope.SYSTEM,
    'github-webhook-secret', 'GitHub webhook signature secret', Secret.fromString(webhookSecret))
def existing = store.getCredentials(Domain.global()).find { it.id == credential.id }
if (existing) {
    store.updateCredentials(Domain.global(), existing, credential)
} else {
    store.addCredentials(Domain.global(), credential)
}
def github = GlobalConfiguration.all().get(GitHubPluginConfig.class)
github.setHookSecretConfig(new HookSecretConfig(credential.id))
github.save()

if (jenkins.getItem('jenkinsJob') == null) {
    def job = jenkins.createProject(FreeStyleProject.class, 'jenkinsJob')
    job.setDescription('Build main after GitHub pushes: validate README and archive tracked source. Replace the build command when application code is added.')
    job.setScm(new GitSCM(
        [new UserRemoteConfig('https://github.com/vvennela/cmpe272-github.git', null, null, null)],
        [new BranchSpec('*/main')], false, [], null, null, []))
    job.addTrigger(new GitHubPushTrigger())
    job.setQuietPeriod(0)
    job.setBuildDiscarder(new LogRotator(-1, 20, -1, 10))
    job.buildersList.add(new Shell('''set -eu
test -s README.md
mkdir -p dist
git archive --format=tar.gz --output=dist/cmpe272-github.tar.gz HEAD
git rev-parse HEAD > dist/commit.txt
echo "Built source archive successfully."
'''))
    job.publishersList.add(new ArtifactArchiver('dist/*'))
    job.save()
}
jenkins.save()
