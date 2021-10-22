from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import time
from ansible.errors import AnsibleError
from ansible.module_utils.urls import open_url, ConnectionError, SSLValidationError
from ansible.module_utils._text import to_native
from ansible.module_utils.six.moves.urllib.error import HTTPError, URLError
from ansible.utils.display import Display

display = Display()


class ApiClient:

    def __init__(self, options={}) -> None:
        self.options = options

    def project(self, project):
        query = {
            'query': """query projectInfo($name: String!) {
        projectByName(name: $name) {
          id
          name
          autoIdle
          branches
          gitUrl
          metadata
          openshift {
            id
            name
          }
          environments {
            name
          }
        }
      }""",
            'variables': '{"name": "%s"}'
        }
        result = self.make_api_call(json.dumps(query) % project)
        if result['data']['projectByName'] == None:
            raise AnsibleError(
                "Unable to get details for project %s; please make sure the project name is correct" % project)
        return result['data']['projectByName']

    def project_from_environment(self, environment):
        query = {
            'query': """query projectInfoFromEnv($name: String!) {
        environmentByKubernetesNamespaceName(kubernetesNamespaceName: $name) {
          project {
            id
            name
            autoIdle
            branches
            gitUrl
            metadata
          }
        }
      }""",
            'variables': '{"name": "%s"}'
        }
        result = self.make_api_call(json.dumps(query) % environment)
        display.v("Project from environment result: %s" % result)
        if result['data']['environmentByKubernetesNamespaceName']['project'] == None:
            raise AnsibleError(
                "Unable to get project details for environment %s; please make sure the environment name is correct" % environment)
        return result['data']['environmentByKubernetesNamespaceName']['project']

    def project_get_variables(self, project):
        query = {
            'query': """query projectVars($name: String!) {
        projectByName(name: $name) {
          envVariables {
            id
            name
            value
            scope
          }
        }
      }""",
            'variables': '{"name": "%s"}'
        }
        result = self.make_api_call(json.dumps(query) % project)
        if result['data']['projectByName'] == None:
            raise AnsibleError(
                "Unable to get variables for %s; please make sure the project name is correct" % project)
        return result['data']['projectByName']['envVariables']

    def project_deploy(self, project, branch, wait=False, delay=60, retries=30):
        query = {
            'query': """mutation deploy($govcms_project: String!, $govcms_branch: String!) {
        deployEnvironmentLatest (input: {
          environment: {
            project: { name: $govcms_project },
            name: $govcms_branch
          }
        })
      }""",
            'variables': '{"govcms_project": "%s", "govcms_branch": "%s"}' %
            (project, branch)
        }
        result = self.make_api_call(json.dumps(query))
        if not wait:
            return result['data']['deployEnvironmentLatest']

        display.display(
            "\033[30;1mWait for deployment completion (%s retries left).\033[0m" % retries)
        return self.project_check_deploy_status(project, branch, delay, retries)

    def project_check_deploy_status(self, project, branch, delay=60, retries=30, current_try=1):
        time.sleep(delay)
        environment = self.environment(
            project + '-' + branch.replace('/', '-'))

        if (len(environment['deployments']) and
            'status' in environment['deployments'][0] and
                environment['deployments'][0]['status'] in ['complete', 'failed', 'new', 'cancelled']):
            return environment['deployments'][0]['status']

        if retries - current_try == 0:
            raise AnsibleError(
                'Maximium number of retries reached; view deployment logs for more information.')

        display.display(
            "\033[30;1mRETRYING: Wait for deployment completion (%s retries left).\033[0m" % (retries - current_try))
        return self.project_check_deploy_status(project, branch, delay, retries, current_try + 1)

    def project_update(self, project_id, patch):
        query = {
            'query': """mutation UpdateProjectDeploymentCluster($projectId: Int!) {
        updateProject(input: {id: $projectId, patch: %s}) {
          id
          name
          autoIdle
          branches
          gitUrl
          metadata
          openshift {
            id
            name
          }
          environments {
            name
          }
        }
      }""" % self.__patch_dict_to_string(patch),
            'variables': '{"projectId": %s}' % project_id
        }
        display.v('Query: %s' % query)
        result = self.make_api_call(json.dumps(query))
        display.v("Project update result: %s" % result)
        return result['data']['updateProject']

    def environment(self, environment):
        query = {
            'query': """query environmentInfo($name: String!) {
        environmentByKubernetesNamespaceName(kubernetesNamespaceName: $name) {
          id
          name
          autoIdle
          deployments {
            name
            status
            started
            completed
          }
          project {
            id
          }
        }
      }""",
            'variables': '{"name": "%s"}'
        }
        result = self.make_api_call(json.dumps(query) % environment)
        if result['data']['environmentByKubernetesNamespaceName'] == None:
            raise AnsibleError(
                "Unable to get details for environment %s; please make sure the environment name is correct" % environment)
        return result['data']['environmentByKubernetesNamespaceName']

    def environment_get_variables(self, environment):
        query = {
            'query': """query envVars($name: String!) {
        environmentByOpenshiftProjectName(openshiftProjectName: $name) {
          envVariables {
            id
            name
            value
            scope
          }
        }
      }""",
            'variables': '{"name": "%s"}'
        }
        result = self.make_api_call(json.dumps(query) % environment)
        if result['data']['environmentByOpenshiftProjectName'] == None:
            raise AnsibleError(
                "Unable to get variables for %s; please make sure the environment name is correct" % environment)
        return result['data']['environmentByOpenshiftProjectName']['envVariables']

    def add_variable(self, type, type_id, name, value, scope):
        query = {
            'query': """mutation AddEnvVar($type: EnvVariableType!, $type_id: Int!, $name: String!, $value: String!, $scope: EnvVariableScope!) {
        addEnvVariable(input: {type: $type, typeId: $type_id, scope: $scope, name: $name, value: $value}) {
          id
        }
      }""",
            'variables': """{
        "type": "%s",
        "type_id": %s,
        "name": "%s",
        "value": "%s",
        "scope": "%s"
      }"""
        }
        result = self.make_api_call(json.dumps(query) % (
            type, type_id, name, value, scope))
        return result['data']['addEnvVariable']['id']

    def delete_variable(self, id):
        query = {
            'query': """mutation DeleteVar($id: Int!) {
        deleteEnvVariable(input:  { id: $id }) }""",
            'variables': '{"id": %s}'
        }
        result = self.make_api_call(json.dumps(query) % id)
        return result['data']['deleteEnvVariable']

    def update_metadata(self, id, key, value):
        query = {
            'query': """mutation UpdateMeta($id: Int!, $key: String!, $value: String!) {
              updateProjectMetadata(input: { id: $id, patch: { key: $key, value: $value }}) {
                  id
              }
          }""",
            'variables': """{
              "id": %s,
              "key": "%s",
              "value": "%s"
          }"""
        }
        result = self.make_api_call(json.dumps(query) % (id, key, value))
        return '%s:%s' % (key, value)

    def remove_metadata(self, id, key):
        query = {
            'query': """mutation RemoveMeta($id: Int!, $key: String!) {
              removeProjectMetadataByKey(input: { id: $id, key: $key }) {
                  id
              }
          }""",
            'variables': """{
              "id": %s,
              "key": "%s"
          }"""
        }
        result = self.make_api_call(json.dumps(query) % (id, key))
        return '%s' % (key)

    def make_api_call(self, payload):
        display.v("Payload: %s" % payload)
        try:
            response = open_url(self.options.get('endpoint'), data=payload,
                                validate_certs=self.options.get(
                                    'validate_certs', False),
                                headers=self.options.get('headers', {}),
                                timeout=self.options.get('timeout', 10))
        except HTTPError as e:
            raise AnsibleError(
                "Received HTTP error: %s" % (to_native(e)))
        except URLError as e:
            raise AnsibleError(
                "Failed lookup url: %s" % (to_native(e)))
        except SSLValidationError as e:
            raise AnsibleError(
                "Error validating the server's certificate: %s" % (to_native(e)))
        except ConnectionError as e:
            raise AnsibleError("Error connecting: %s" % (to_native(e)))

        return json.loads(response.read())

    def __patch_dict_to_string(self, patch):
        value_list = []
        for key, value in patch.items():
            value_item = key + ': '
            if type(value) is int:
                value_item += str(value)
            else:
                try:
                    value = int(value)
                    value_item += str(value)
                except ValueError:
                    value_item += '"' + value + '"'
            value_list.append(value_item)
        return '{' + ', '.join(value_list) + '}'