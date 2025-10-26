pipeline {
    agent any

    parameters {
        choice(
            name: 'BRANCH',
            choices: ['main', 'develop', 'staging', 'production'],
            description: 'Select branch to build'
        )
        string(
            name: 'DOCKER_TAG',
            defaultValue: 'latest',
            description: 'Docker image tag'
        )
        choice(
            name: 'DEPLOY',
            choices: ['yes', 'no'],
            description: 'Deploy to Kubernetes?'
        )
    }

    environment {
        DOCKER_HUB_CREDENTIALS = credentials('dockerhub')
        DOCKER_IMAGE = "algoroot05/pythonapp"
        IMAGE_TAG = "${params.DOCKER_TAG}"
        IMAGE_FULL = "${DOCKER_IMAGE}:${IMAGE_TAG}"
        BUILD_TAG = "${params.BRANCH}-${BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    echo "🔄 Checking out branch: ${params.BRANCH}"
                    checkout([
                        $class: 'GitSCM',
                        branches: [[name: "*/${params.BRANCH}"]],
                        userRemoteConfigs: [[
                            url: 'https://github.com/algorootprod/algojobs_service.git',
                            credentialsId: 'github'
                        ]]
                    ])
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "🐍 Building Python Docker image..."
                    sh """
                        docker build -t ${IMAGE_FULL} .
                        docker tag ${IMAGE_FULL} ${DOCKER_IMAGE}:${BUILD_TAG}
                    """
                }
            }
        }

        stage('Push to Docker Hub') {
            steps {
                script {
                    echo "📤 Pushing image to Docker Hub..."
                    sh """
                        echo \${DOCKER_HUB_CREDENTIALS_PSW} | docker login -u \${DOCKER_HUB_CREDENTIALS_USR} --password-stdin
                        docker push ${IMAGE_FULL}
                        docker push ${DOCKER_IMAGE}:${BUILD_TAG}
                        docker logout
                    """
                }
            }
        }

        stage('Deploy to Kubernetes') {
            when {
                expression { params.DEPLOY == 'yes' }
            }
            steps {
                script {
                    echo "🚀 Deploying Python app to Kubernetes..."
                    sh """
                        microk8s kubectl set image deployment/pythonapp \
                            pythonapp=${IMAGE_FULL} -n nodeapp || true

                        microk8s kubectl rollout restart deployment/pythonapp -n nodeapp
                        microk8s kubectl rollout status deployment/pythonapp -n nodeapp --timeout=5m

                        echo "=== Pods Status ==="
                        microk8s kubectl get pods -n nodeapp
                    """
                }
            }
        }
    }

    post {
        success {
            echo """
            ✅ Build Successful!
            🐳 Image: ${IMAGE_FULL}
            🏷️ Build Tag: ${DOCKER_IMAGE}:${BUILD_TAG}
            """
        }
        failure {
            echo """
            ❌ Build Failed!
            🐳 Image: ${IMAGE_FULL}
            """
        }
        always {
            sh """
                docker rmi ${IMAGE_FULL} || true
                docker rmi ${DOCKER_IMAGE}:${BUILD_TAG} || true
                docker system prune -f || true
            """
        }
    }
}
