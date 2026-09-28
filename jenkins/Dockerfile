FROM jenkins/jenkins:lts-jdk21
RUN jenkins-plugin-cli --plugins github git plain-credentials
COPY init.groovy /usr/share/jenkins/ref/init.groovy.d/01-setup.groovy
