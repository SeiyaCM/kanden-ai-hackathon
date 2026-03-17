/**
 * ApiGatewayToIot Construct
 *
 * aws-solutions-constructs/aws-apigateway-iot をベースに、
 * 最新 CDK (v2.242+) 向けに @aws-solutions-constructs/core 依存を
 * インライン化したもの。
 *
 * 元ソース: https://github.com/awslabs/aws-solutions-constructs (Apache-2.0)
 */

import * as cdk from 'aws-cdk-lib';
import * as api from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import deepmerge = require('deepmerge');

// ─── コアヘルパー (インライン) ──────────────────────────────────────────────

function isPlainObject(o: object): boolean {
  if (Array.isArray(o)) return true;
  if (o === null || typeof o !== 'object') return false;
  const ctor = (o as { constructor?: unknown }).constructor;
  if (typeof ctor !== 'function') return false;
  const prot = (ctor as { prototype?: unknown }).prototype;
  if (typeof prot !== 'object' || prot === null) return false;
  return Object.prototype.hasOwnProperty.call(prot, 'isPrototypeOf') as boolean;
}

function consolidateProps(defaultProps: object, clientProps?: object, constructProps?: object): object {
  let result: object = defaultProps;
  if (clientProps) {
    result = deepmerge(result, clientProps, {
      arrayMerge: (_dst, src) => src,
      isMergeableObject: isPlainObject,
    });
  }
  if (constructProps) {
    result = deepmerge(result, constructProps, {
      arrayMerge: (_dst, src) => src,
      isMergeableObject: isPlainObject,
    });
  }
  return result;
}

interface CfnNagMetadata {
  cfn_nag?: { rules_to_suppress?: { id: string; reason: string }[] };
  guard?: { SuppressedRules?: string[] };
}

function addCfnSuppressRules(resource: cdk.Resource | cdk.CfnResource, rules: { id: string; reason: string }[]) {
  const cfnResource = resource instanceof cdk.Resource
    ? (resource.node.defaultChild as cdk.CfnResource)
    : resource;
  const meta = cfnResource.cfnOptions.metadata as CfnNagMetadata | undefined;
  if (meta?.cfn_nag?.rules_to_suppress) {
    meta.cfn_nag.rules_to_suppress.push(...rules);
  } else {
    cfnResource.addMetadata('cfn_nag', { rules_to_suppress: rules });
  }
}

function addCfnGuardSuppressRules(resource: cdk.Resource | cdk.CfnResource, rules: string[]) {
  const cfnResource = resource instanceof cdk.Resource
    ? (resource.node.findChild('Resource') as cdk.CfnResource)
    : resource;
  const meta = cfnResource.cfnOptions?.metadata as CfnNagMetadata | undefined;
  if (meta?.guard?.SuppressedRules) {
    meta.guard.SuppressedRules.push(...rules);
  } else {
    cfnResource.addMetadata('guard', { SuppressedRules: rules });
  }
}

function buildLogGroup(scope: Construct, logGroupId: string, logGroupProps?: logs.LogGroupProps): logs.LogGroup {
  const props: logs.LogGroupProps = consolidateProps(
    { retention: logs.RetentionDays.INFINITE },
    logGroupProps,
  );
  const logGroup = new logs.LogGroup(scope, logGroupId, props);
  if (props.retention === logs.RetentionDays.INFINITE) {
    addCfnSuppressRules(logGroup, [{
      id: 'W86',
      reason: "Retention period for CloudWatchLogs LogGroups are set to 'Never Expire' to preserve customer data indefinitely",
    }]);
  }
  if (!props.encryptionKey) {
    addCfnSuppressRules(logGroup, [{
      id: 'W84',
      reason: 'By default CloudWatchLogs LogGroups data is encrypted using the CloudWatch server-side encryption keys (AWS Managed Keys)',
    }]);
  }
  return logGroup;
}

function configureCloudwatchRoleForApi(scope: Construct, restApi: api.RestApiBase): iam.Role {
  const role = new iam.Role(scope, 'LambdaRestApiCloudWatchRole', {
    assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
    inlinePolicies: {
      LambdaRestApiCloudWatchRolePolicy: new iam.PolicyDocument({
        statements: [new iam.PolicyStatement({
          actions: [
            'logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:DescribeLogGroups',
            'logs:DescribeLogStreams', 'logs:PutLogEvents', 'logs:GetLogEvents', 'logs:FilterLogEvents',
          ],
          resources: [`arn:${cdk.Aws.PARTITION}:logs:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:*`],
        })],
      }),
    },
  });

  const cfnApi = restApi.node.findChild('Resource') as api.CfnRestApi;
  const cfnAccount = new api.CfnAccount(scope, 'LambdaRestApiAccount', {
    cloudWatchRoleArn: role.roleArn,
  });
  cfnAccount.addDependency(cfnApi);

  const deployment = restApi.latestDeployment?.node.findChild('Resource') as api.CfnDeployment;
  addCfnSuppressRules(deployment, [{
    id: 'W45',
    reason: 'ApiGateway has AccessLogging enabled in AWS::ApiGateway::Stage resource, but cfn_nag checks for it in AWS::ApiGateway::Deployment resource',
  }]);
  addCfnGuardSuppressRules(role, ['IAM_NO_INLINE_POLICY_CHECK']);

  return role;
}

function buildGlobalRestApi(
  scope: Construct,
  apiGatewayProps?: api.RestApiProps,
  logGroupProps?: logs.LogGroupProps,
  createUsagePlan: boolean = true,
): { api: api.RestApi; role?: iam.Role; logGroup: logs.LogGroup } {
  const logGroup = buildLogGroup(scope, 'ApiAccessLogGroup', logGroupProps);

  const defaultProps: api.RestApiProps = {
    endpointConfiguration: { types: [api.EndpointType.EDGE] },
    cloudWatchRole: false,
    deployOptions: {
      accessLogDestination: new api.LogGroupLogDestination(logGroup),
      accessLogFormat: api.AccessLogFormat.jsonWithStandardFields(),
      loggingLevel: api.MethodLoggingLevel.INFO,
      dataTraceEnabled: false,
      tracingEnabled: true,
    },
    defaultMethodOptions: {
      authorizationType: api.AuthorizationType.IAM,
    },
  };

  const consolidatedProps = consolidateProps(defaultProps, apiGatewayProps, { cloudWatchRole: false });
  const restApi = new api.RestApi(scope, 'RestApi', consolidatedProps);

  addCfnGuardSuppressRules(restApi.deploymentStage, ['API_GW_CACHE_ENABLED_AND_ENCRYPTED']);

  const role = (apiGatewayProps?.cloudWatchRole !== false)
    ? configureCloudwatchRoleForApi(scope, restApi)
    : undefined;

  if (createUsagePlan) {
    const plan = restApi.addUsagePlan('UsagePlan', {
      apiStages: [{ api: restApi, stage: restApi.deploymentStage }],
    });
    if (apiGatewayProps?.defaultMethodOptions?.apiKeyRequired === true) {
      const key = restApi.addApiKey('ApiKey');
      plan.addApiKey(key);
    }
  }

  return { api: restApi, role, logGroup };
}

// ─── インターフェース ────────────────────────────────────────────────────────

export interface ApiGatewayToIotProps {
  /** AWS IoT エンドポイントのサブドメイン (例: ab123cdefghij4l-ats) */
  readonly iotEndpoint: string;
  /** API Key を作成して UsagePlan に関連付けるか */
  readonly apiGatewayCreateApiKey?: boolean;
  /** API Gateway が使用する IAM ロール (未指定時は自動作成) */
  readonly apiGatewayExecutionRole?: iam.IRole;
  /** API Gateway のプロパティを上書き */
  readonly apiGatewayProps?: api.RestApiProps;
  /** UsagePlan を作成するか (デフォルト: true) */
  readonly createUsagePlan?: boolean;
  /** CloudWatch Logs の LogGroup プロパティ */
  readonly logGroupProps?: logs.LogGroupProps;
}

// ─── コンストラクト ──────────────────────────────────────────────────────────

export class ApiGatewayToIot extends Construct {
  public readonly apiGateway: api.RestApi;
  public readonly apiGatewayCloudWatchRole?: iam.Role;
  public readonly apiGatewayLogGroup: logs.LogGroup;
  public readonly apiGatewayRole: iam.IRole;

  private readonly iotEndpoint: string;
  private readonly requestValidator: api.IRequestValidator;
  // IoT Core トピックのネスト上限: スラッシュ7つまで
  private readonly topicNestingLevel = 7;

  constructor(scope: Construct, id: string, props: ApiGatewayToIotProps) {
    super(scope, id);

    // props バリデーション
    if (!props.createUsagePlan && props.apiGatewayProps?.defaultMethodOptions?.apiKeyRequired) {
      throw new Error('Error - if API key is required, then the Usage plan must be created');
    }

    this.iotEndpoint = props.iotEndpoint.trim().split('.')[0];
    if (!this.iotEndpoint || this.iotEndpoint.length === 0) {
      throw new Error('specify a valid iotEndpoint');
    }

    // API Gateway 追加プロパティ
    const extraApiGwProps = consolidateProps(
      {
        binaryMediaTypes: ['application/octet-stream'],
        defaultMethodOptions: { apiKeyRequired: props.apiGatewayCreateApiKey },
      },
      props.apiGatewayProps,
    );

    // IAM ロール
    if (props.apiGatewayExecutionRole) {
      this.apiGatewayRole = props.apiGatewayExecutionRole;
    } else {
      const policyDocument = iam.PolicyDocument.fromJson({
        Version: '2012-10-17',
        Statement: [
          {
            Action: ['iot:UpdateThingShadow'],
            Resource: `arn:${cdk.Aws.PARTITION}:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:thing/*`,
            Effect: 'Allow',
          },
          {
            Action: ['iot:Publish'],
            Resource: `arn:${cdk.Aws.PARTITION}:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/*`,
            Effect: 'Allow',
          },
        ],
      });

      const role = new iam.Role(this, 'apigateway-iot-role', {
        assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
        path: '/',
        inlinePolicies: { awsapigatewayiotpolicy: policyDocument },
      });
      addCfnGuardSuppressRules(role, ['IAM_NO_INLINE_POLICY_CHECK']);
      this.apiGatewayRole = role;
    }

    // API Gateway 構築
    const globalRestApiResponse = buildGlobalRestApi(
      this,
      extraApiGwProps,
      props.logGroupProps,
      props.createUsagePlan ?? true,
    );
    this.apiGateway = globalRestApiResponse.api;
    this.apiGatewayCloudWatchRole = globalRestApiResponse.role;
    this.apiGatewayLogGroup = globalRestApiResponse.logGroup;

    // リクエストバリデーター
    this.requestValidator = new api.RequestValidator(this, 'aws-apigateway-iot-req-val', {
      restApi: this.apiGateway,
      validateRequestBody: false,
      validateRequestParameters: true,
    });

    // /message/{topic-level-1}/.../{topic-level-7} リソース
    const msgResource = this.apiGateway.root.addResource('message');
    let topicPath = 'topics';
    let parentNode: api.IResource = msgResource;
    let integParams: { [key: string]: string } = {};
    let methodParams: { [key: string]: boolean } = {};

    for (let level = 1; level <= this.topicNestingLevel; level++) {
      const topicName = `topic-level-${level}`;
      const topicResource = parentNode.addResource(`{${topicName}}`);
      integParams = { ...integParams, [`integration.request.path.${topicName}`]: `method.request.path.${topicName}` };
      methodParams = { ...methodParams, [`method.request.path.${topicName}`]: true };
      topicPath = `${topicPath}/{${topicName}}`;
      this.addResourceMethod(topicResource, props, topicPath, integParams, methodParams);
      parentNode = topicResource;
    }

    // /shadow/{thingName} リソース
    const shadowResource = this.apiGateway.root.addResource('shadow');
    const defaultShadowResource = shadowResource.addResource('{thingName}');
    const shadowIntegParams = { 'integration.request.path.thingName': 'method.request.path.thingName' };
    const shadowMethodParams = { 'method.request.path.thingName': true };
    this.addResourceMethod(defaultShadowResource, props, 'things/{thingName}/shadow', shadowIntegParams, shadowMethodParams);

    // /shadow/{thingName}/{shadowName} リソース
    const namedShadowResource = defaultShadowResource.addResource('{shadowName}');
    const namedShadowIntegParams = {
      ...shadowIntegParams,
      'integration.request.path.shadowName': 'method.request.path.shadowName',
    };
    const namedShadowMethodParams = {
      ...shadowMethodParams,
      'method.request.path.shadowName': true,
    };
    this.addResourceMethod(
      namedShadowResource,
      props,
      'things/{thingName}/shadow?name={shadowName}',
      namedShadowIntegParams,
      namedShadowMethodParams,
    );
  }

  private addResourceMethod(
    resource: api.IResource,
    props: ApiGatewayToIotProps,
    resourcePath: string,
    integReqParams: { [key: string]: string },
    methodReqParams: { [key: string]: boolean },
  ) {
    const integResp: api.IntegrationResponse[] = [
      { statusCode: '200', selectionPattern: '2\\d{2}', responseTemplates: { 'application/json': "$input.json('$')" } },
      { statusCode: '500', selectionPattern: '5\\d{2}', responseTemplates: { 'application/json': "$input.json('$')" } },
      { statusCode: '403', responseTemplates: { 'application/json': "$input.json('$')" } },
    ];

    const methodResp: api.MethodResponse[] = [
      { statusCode: '200' },
      { statusCode: '500' },
      { statusCode: '403' },
    ];

    const baseIntegrationProps: api.AwsIntegrationProps = {
      service: 'iotdata',
      path: resourcePath,
      subdomain: this.iotEndpoint,
      integrationHttpMethod: 'POST',
      options: {
        credentialsRole: this.apiGatewayRole,
        requestParameters: {
          "integration.request.header.Content-Type": "'application/json'",
          ...integReqParams,
        },
        requestTemplates: { 'application/json': "$input.json('$')" },
        integrationResponses: integResp,
        passthroughBehavior: api.PassthroughBehavior.WHEN_NO_MATCH,
      },
    };

    const integration = new api.AwsIntegration(baseIntegrationProps);

    const methodOptions: api.MethodOptions = {
      requestParameters: methodReqParams,
      methodResponses: methodResp,
      requestValidator: this.requestValidator,
    };

    const method = resource.addMethod('POST', integration, methodOptions);

    if (props.apiGatewayCreateApiKey === true) {
      addCfnSuppressRules(method, [{
        id: 'W59',
        reason: 'When ApiKey is being created, we also set apikeyRequired to true, so technically apiGateway still looks for apiKey even though user specified AuthorizationType to NONE',
      }]);
    }
  }
}
