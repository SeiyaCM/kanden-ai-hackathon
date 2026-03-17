import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import type { Construct } from 'constructs';

// IoT Core へのパブリッシュ先トピック
const IOT_TOPIC = 'kanden/fatigue';

export class IacStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const iotEndpoint = 'aw72vo0duw05s-ats';

    // ─── IAM Role: API Gateway → IoT Core ────────────────────────────────────
    const apiGwIotRole = new iam.Role(this, 'ApiGwIotRole', {
      assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      inlinePolicies: {
        IotPublishPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['iot:Publish'],
              resources: [
                `arn:${cdk.Aws.PARTITION}:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/${IOT_TOPIC}`,
              ],
            }),
          ],
        }),
      },
    });

    // ─── API Gateway ─────────────────────────────────────────────────────────
    const apiLogGroup = new logs.LogGroup(this, 'ApiAccessLogGroup', {
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const restApi = new apigateway.RestApi(this, 'FatigueApi', {
      restApiName: '空間AIブレイン-疲労度検知API',
      description: 'デバイス（DGX Spark）からエンジニアの疲労度データを受信し IoT Core へパブリッシュ',
      deployOptions: {
        stageName: 'v1',
        accessLogDestination: new apigateway.LogGroupLogDestination(apiLogGroup),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields(),
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: false,
        tracingEnabled: true,
      },
      defaultMethodOptions: {
        apiKeyRequired: true,
      },
    });

    // ─── POST /fatigue → IoT Core 直接統合 ───────────────────────────────────
    // API Gateway が IoT Core の HTTPS エンドポイント (iotdata) へ直接 POST
    // パス: topics/<topic> → IoT Core の Publish エンドポイント
    const iotIntegration = new apigateway.AwsIntegration({
      service: 'iotdata',
      subdomain: iotEndpoint,                  // <iotEndpoint>.iot.<region>.amazonaws.com
      path: `topics/${IOT_TOPIC}`,
      integrationHttpMethod: 'POST',
      options: {
        credentialsRole: apiGwIotRole,
        requestParameters: {
          'integration.request.header.Content-Type': "'application/json'",
        },
        requestTemplates: {
          // openapi.yml の FatiguePayload をそのまま IoT Core へ転送
          'application/json': "$input.json('$')",
        },
        integrationResponses: [
          {
            statusCode: '200',
            selectionPattern: '2\\d{2}',
            responseTemplates: {
              'application/json': JSON.stringify({
                status: 'accepted',
                timestamp: "$context.requestTime",
              }),
            },
          },
          {
            statusCode: '400',
            selectionPattern: '4\\d{2}',
            responseTemplates: {
              'application/json': JSON.stringify({
                error: 'Bad Request',
                message: "$input.path('$.message')",
              }),
            },
          },
          {
            statusCode: '500',
            selectionPattern: '5\\d{2}',
            responseTemplates: {
              'application/json': JSON.stringify({
                error: 'Internal Server Error',
                message: 'An unexpected error occurred',
              }),
            },
          },
        ],
        passthroughBehavior: apigateway.PassthroughBehavior.WHEN_NO_MATCH,
      },
    });

    restApi.root.addResource('fatigue').addMethod('POST', iotIntegration, {
      methodResponses: [
        { statusCode: '200' },
        { statusCode: '400' },
        { statusCode: '500' },
      ],
      requestValidator: new apigateway.RequestValidator(this, 'BodyValidator', {
        restApi,
        validateRequestBody: true,
        validateRequestParameters: false,
      }),
      requestModels: {
        'application/json': new apigateway.Model(this, 'FatiguePayloadModel', {
          restApi,
          contentType: 'application/json',
          description: 'openapi.yml FatiguePayload スキーマ',
          schema: {
            schema: apigateway.JsonSchemaVersion.DRAFT4,
            type: apigateway.JsonSchemaType.OBJECT,
            required: ['device_id', 'user_id', 'timestamp', 'fatigue_score'],
            properties: {
              device_id:     { type: apigateway.JsonSchemaType.STRING },
              user_id:       { type: apigateway.JsonSchemaType.STRING },
              timestamp:     { type: apigateway.JsonSchemaType.STRING },
              fatigue_score: {
                type: apigateway.JsonSchemaType.NUMBER,
                minimum: 0.0,
                maximum: 1.0,
              },
              modalities: { type: apigateway.JsonSchemaType.OBJECT },
              metadata:   { type: apigateway.JsonSchemaType.OBJECT },
            },
          },
        }),
      },
    });

    // ─── API Key + Usage Plan ─────────────────────────────────────────────────
    const apiKey = restApi.addApiKey('FatigueApiKey', {
      apiKeyName: 'fatigue-api-key',
      description: 'DGX Spark デバイス用 API キー',
    });

    restApi.addUsagePlan('FatigueUsagePlan', {
      name: 'FatigueUsagePlan',
      apiStages: [{ api: restApi, stage: restApi.deploymentStage }],
      throttle: { rateLimit: 100, burstLimit: 200 },
    }).addApiKey(apiKey);

    // ─── Outputs ─────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'PostFatigueEndpoint', {
      value: `${restApi.url}fatigue`,
      description: 'POST /fatigue エンドポイント (x-api-key ヘッダーに API キーを付与)',
    });

    new cdk.CfnOutput(this, 'ApiKeyId', {
      value: apiKey.keyId,
      description: 'API Key ID (aws apigateway get-api-key --api-key <id> --include-value で値を取得)',
    });

    new cdk.CfnOutput(this, 'IotTopic', {
      value: IOT_TOPIC,
      description: 'IoT Core パブリッシュ先 MQTT トピック',
    });
  }
}
