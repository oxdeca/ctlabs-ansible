#!groovy

# ------------------------------------------------------------------------------
# File        : ctlabs-ansible/roles/ctlabs_jenkins/files/ctlabs-user.groovy
# Description : Create Default user
# ------------------------------------------------------------------------------

import jenkins.model.*
import hudson.security.*

def instance = Jenkins.getInstance()

println "--> creating local user 'ctlabs'"

def hudsonRealm = new HudsonPrivateSecurityRealm(false)
hudsonRealm.createAccount('ctlabs','secret123!')
instance.setSecurityRealm(hudsonRealm)

def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
instance.setAuthorizationStrategy(strategy)
instance.save()
