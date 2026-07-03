# Alibaba Cloud Terraform provider catalog

Total entries: **140** (resources: 79, data sources: 61; deprecated: 117; normal resources omitted: 1041; non-common data sources omitted: 673; source entries: 1854).

Built from `aliyun/terraform-provider-alicloud@master` by `scripts/build_alicloud_providers.py`. Re-run the script to refresh.

This is a stale-tolerant local cache for common data source names, deprecation routing, and doc URL fallback. IaCService metadata is authoritative for current resource availability. Normal supported resources and non-common data sources are intentionally omitted to avoid stale catalog blocking and context bloat.

Columns — **type** (resource / data source), **name** (`alicloud_*`), **status** (empty = supported; `DEPRECATED -> alicloud_X` = deprecated, use X; `DEPRECATED` = deprecated without a direct replacement), **doc** (GitHub source, used as a Step 4.2 fallback when MCP documentation lookup is insufficient).

## Actiontrail

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_actiontrails` | DEPRECATED -> `alicloud_actiontrail_trails` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/actiontrails.html.markdown) |
| resource | `alicloud_actiontrail` | DEPRECATED -> `alicloud_actiontrail_trail` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/actiontrail.html.markdown) |

## Alidns

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_dns_domains` | DEPRECATED -> `alicloud_alidns_domains` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/dns_domains.html.markdown) |
| data source | `alicloud_dns_instances` | DEPRECATED -> `alicloud_alidns_instances` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/dns_instances.html.markdown) |
| resource | `alicloud_dns` | DEPRECATED -> `alicloud_alidns_domain` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/dns.html.markdown) |
| resource | `alicloud_dns_domain` | DEPRECATED -> `alicloud_alidns_domain` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/dns_domain.html.markdown) |
| resource | `alicloud_dns_domain_attachment` | DEPRECATED -> `alicloud_alidns_domain_attachment` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/dns_domain_attachment.html.markdown) |
| resource | `alicloud_dns_group` | DEPRECATED -> `alicloud_alidns_domain_group` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/dns_group.html.markdown) |
| resource | `alicloud_dns_instance` | DEPRECATED -> `alicloud_alidns_instance` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/dns_instance.html.markdown) |
| resource | `alicloud_dns_record` | DEPRECATED -> `alicloud_alidns_record` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/dns_record.html.markdown) |

## AnalyticDB for MySQL (ADB)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_adb_clusters` | DEPRECATED -> `alicloud_adb_db_clusters` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/adb_clusters.html.markdown) |
| resource | `alicloud_adb_cluster` | DEPRECATED -> `alicloud_adb_db_cluster` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/adb_cluster.html.markdown) |

## AnalyticDB for PostgreSQL (GPDB)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_gpdb_elastic_instance` | DEPRECATED -> `alicloud_gpdb_instance` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/gpdb_elastic_instance.html.markdown) |

## Application Load Balancer (ALB)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_alb_load_balancers` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/alb_load_balancers.html.markdown) |
| data source | `alicloud_alb_server_groups` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/alb_server_groups.html.markdown) |

## Application Real-Time Monitoring Service (ARMS)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_arms_prometheis` | DEPRECATED -> `alicloud_arms_prometheus` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/arms_prometheis.html.markdown) |
| data source | `alicloud_arms_remote_writes` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/arms_remote_writes.html.markdown) |
| resource | `alicloud_arms_remote_write` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/arms_remote_write.html.markdown) |

## Apsara Devops(RDC)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_rdc_organizations` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/rdc_organizations.html.markdown) |
| resource | `alicloud_rdc_organization` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/rdc_organization.html.markdown) |

## ApsaraDB for MyBase (CDDC)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_cddc_dedicated_host` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cddc_dedicated_host.html.markdown) |
| resource | `alicloud_cddc_dedicated_host_account` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cddc_dedicated_host_account.html.markdown) |
| resource | `alicloud_cddc_dedicated_host_group` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cddc_dedicated_host_group.html.markdown) |
| resource | `alicloud_cddc_dedicated_propre_host` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cddc_dedicated_propre_host.html.markdown) |

## Brain Industrial

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_brain_industrial_pid_loops` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/brain_industrial_pid_loops.html.markdown) |
| data source | `alicloud_brain_industrial_pid_organizations` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/brain_industrial_pid_organizations.html.markdown) |
| data source | `alicloud_brain_industrial_pid_projects` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/brain_industrial_pid_projects.html.markdown) |
| data source | `alicloud_brain_industrial_service` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/brain_industrial_service.html.markdown) |
| resource | `alicloud_brain_industrial_pid_loop` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/brain_industrial_pid_loop.html.markdown) |
| resource | `alicloud_brain_industrial_pid_organization` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/brain_industrial_pid_organization.html.markdown) |
| resource | `alicloud_brain_industrial_pid_project` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/brain_industrial_pid_project.html.markdown) |

## Cassandra

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_cassandra_backup_plans` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cassandra_backup_plans.html.markdown) |
| data source | `alicloud_cassandra_clusters` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cassandra_clusters.html.markdown) |
| data source | `alicloud_cassandra_data_centers` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cassandra_data_centers.html.markdown) |
| data source | `alicloud_cassandra_zones` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cassandra_zones.html.markdown) |
| resource | `alicloud_cassandra_backup_plan` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cassandra_backup_plan.html.markdown) |
| resource | `alicloud_cassandra_cluster` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cassandra_cluster.html.markdown) |
| resource | `alicloud_cassandra_data_center` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cassandra_data_center.html.markdown) |

## Certificate Management Service (Original SSL Certificate)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_cas_certificates` | DEPRECATED -> `alicloud_ssl_certificates_service_certificates` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cas_certificates.html.markdown) |
| resource | `alicloud_cas_certificate` | DEPRECATED -> `alicloud_ssl_certificates_service_certificate` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cas_certificate.html.markdown) |

## Classic Load Balancer (SLB)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_slb_load_balancers` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/slb_load_balancers.html.markdown) |
| data source | `alicloud_slbs` | DEPRECATED -> `alicloud_slb_load_balancers` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/slbs.html.markdown) |
| resource | `alicloud_slb` | DEPRECATED -> `alicloud_slb_load_balancer` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/slb.html.markdown) |
| resource | `alicloud_slb_attachment` | DEPRECATED -> `alicloud_slb_backend_server` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/slb_attachment.html.markdown) |

## Cloud Config (Config)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_config_delivery_channels` | DEPRECATED -> `alicloud_config_deliveries` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/config_delivery_channels.html.markdown) |
| resource | `alicloud_config_delivery_channel` | DEPRECATED -> `alicloud_config_delivery` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/config_delivery_channel.html.markdown) |

## Cloud Firewall

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_cloud_firewall_instance` | DEPRECATED -> `alicloud_cloud_firewall_instance_v2` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cloud_firewall_instance.html.markdown) |

## Cloud Monitor Service

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_cms_service` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cms_service.html.markdown) |

## Container Registry (CR)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_cr_namespaces` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cr_namespaces.html.markdown) |
| data source | `alicloud_cr_repos` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cr_repos.html.markdown) |
| resource | `alicloud_cr_namespace` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cr_namespace.html.markdown) |
| resource | `alicloud_cr_repo` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cr_repo.html.markdown) |

## Container Service for Kubernetes (ACK)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_cs_clusters` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cs_clusters.html.markdown) |
| data source | `alicloud_cs_edge_kubernetes_clusters` | DEPRECATED -> `alicloud_cs_clusters` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cs_edge_kubernetes_clusters.html.markdown) |
| data source | `alicloud_cs_kubernetes_clusters` | DEPRECATED -> `alicloud_cs_clusters` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cs_kubernetes_clusters.html.markdown) |
| data source | `alicloud_cs_managed_kubernetes_clusters` | DEPRECATED -> `alicloud_cs_clusters` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cs_managed_kubernetes_clusters.html.markdown) |
| data source | `alicloud_cs_serverless_kubernetes_clusters` | DEPRECATED -> `alicloud_cs_clusters` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/cs_serverless_kubernetes_clusters.html.markdown) |
| resource | `alicloud_cs_edge_kubernetes` | DEPRECATED -> `alicloud_cs_managed_kubernetes` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cs_edge_kubernetes.html.markdown) |
| resource | `alicloud_cs_kubernetes` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cs_kubernetes.html.markdown) |
| resource | `alicloud_cs_kubernetes_autoscaler` | DEPRECATED -> `alicloud_cs_autoscaling_config` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cs_kubernetes_autoscaler.html.markdown) |
| resource | `alicloud_cs_serverless_kubernetes` | DEPRECATED -> `alicloud_cs_managed_kubernetes` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/cs_serverless_kubernetes.html.markdown) |

## DAS

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_das_switch_das_pro` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/das_switch_das_pro.html.markdown) |

## E-MapReduce (EMR)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_emr_clusters` | DEPRECATED -> `alicloud_emrv2_clusters` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/emr_clusters.html.markdown) |
| resource | `alicloud_emr_cluster` | DEPRECATED -> `alicloud_emrv2_cluster` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/emr_cluster.html.markdown) |

## ECS

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_disks` | DEPRECATED -> `alicloud_ecs_disks` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/disks.html.markdown) |
| data source | `alicloud_images` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/images.html.markdown) |
| data source | `alicloud_instance_types` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/instance_types.html.markdown) |
| data source | `alicloud_instances` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/instances.html.markdown) |
| data source | `alicloud_key_pairs` | DEPRECATED -> `alicloud_ecs_key_pairs` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/key_pairs.html.markdown) |
| data source | `alicloud_network_interfaces` | DEPRECATED -> `alicloud_ecs_network_interfaces` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/network_interfaces.html.markdown) |
| data source | `alicloud_regions` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/regions.html.markdown) |
| data source | `alicloud_security_groups` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/security_groups.html.markdown) |
| data source | `alicloud_snapshots` | DEPRECATED -> `alicloud_ecs_snapshots` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/snapshots.html.markdown) |
| data source | `alicloud_zones` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/zones.html.markdown) |
| resource | `alicloud_disk` | DEPRECATED -> `alicloud_ecs_disk` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/disk.html.markdown) |
| resource | `alicloud_disk_attachment` | DEPRECATED -> `alicloud_ecs_disk_attachment` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/disk_attachment.html.markdown) |
| resource | `alicloud_key_pair` | DEPRECATED -> `alicloud_ecs_key_pair` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/key_pair.html.markdown) |
| resource | `alicloud_key_pair_attachment` | DEPRECATED -> `alicloud_ecs_key_pair_attachment` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/key_pair_attachment.html.markdown) |
| resource | `alicloud_launch_template` | DEPRECATED -> `alicloud_ecs_launch_template` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/launch_template.html.markdown) |
| resource | `alicloud_network_interface` | DEPRECATED -> `alicloud_ecs_network_interface` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/network_interface.html.markdown) |
| resource | `alicloud_network_interface_attachment` | DEPRECATED -> `alicloud_ecs_network_interface_attachment` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/network_interface_attachment.html.markdown) |
| resource | `alicloud_ram_role_attachment` | DEPRECATED -> `alicloud_ecs_ram_role_attachment` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/ram_role_attachment.html.markdown) |
| resource | `alicloud_snapshot` | DEPRECATED -> `alicloud_ecs_snapshot` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/snapshot.html.markdown) |
| resource | `alicloud_snapshot_policy` | DEPRECATED -> `alicloud_ecs_auto_snapshot_policy` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/snapshot_policy.html.markdown) |

## Elastic Desktop Service (ECD)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_ecd_ram_directory` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/ecd_ram_directory.html.markdown) |

## Elastic High Performance Computing (Ehpc)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_ehpc_cluster` | DEPRECATED -> `alicloud_ehpc_cluster_v2` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/ehpc_cluster.html.markdown) |

## Elastic IP Address (EIP)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_eips` | DEPRECATED -> `alicloud_eip_addresses` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/eips.html.markdown) |
| resource | `alicloud_eip` | DEPRECATED -> `alicloud_eip_address` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/eip.html.markdown) |

## Event Bridge

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_event_bridge_event_source` | DEPRECATED -> `alicloud_event_bridge_event_source_v2` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/event_bridge_event_source.html.markdown) |

## Express Connect

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_router_interfaces` | DEPRECATED -> `alicloud_express_connect_router_interfaces` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/router_interfaces.html.markdown) |
| resource | `alicloud_router_interface` | DEPRECATED -> `alicloud_express_connect_router_interface` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/router_interface.html.markdown) |
| resource | `alicloud_router_interface_connection` | DEPRECATED -> `alicloud_express_connect_router_interface` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/router_interface_connection.html.markdown) |

## Function Compute Service (FC)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_fc_alias` | DEPRECATED -> `alicloud_fcv3_alias` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/fc_alias.html.markdown) |
| resource | `alicloud_fc_custom_domain` | DEPRECATED -> `alicloud_fcv3_custom_domain` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/fc_custom_domain.html.markdown) |
| resource | `alicloud_fc_function` | DEPRECATED -> `alicloud_fcv3_function` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/fc_function.html.markdown) |
| resource | `alicloud_fc_function_async_invoke_config` | DEPRECATED -> `alicloud_fcv3_async_invoke_config` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/fc_function_async_invoke_config.html.markdown) |
| resource | `alicloud_fc_layer_version` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/fc_layer_version.html.markdown) |
| resource | `alicloud_fc_service` | DEPRECATED -> `alicloud_fcv3_function` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/fc_service.html.markdown) |
| resource | `alicloud_fc_trigger` | DEPRECATED -> `alicloud_fcv3_trigger` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/fc_trigger.html.markdown) |

## Function Compute Service V3 (FCV3)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_fcv3_functions` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/fcv3_functions.html.markdown) |
| data source | `alicloud_fcv3_triggers` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/fcv3_triggers.html.markdown) |

## Hybrid Backup Recovery (HBR)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_hbr_ecs_backup_plan` | DEPRECATED -> `alicloud_hbr_policy` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/hbr_ecs_backup_plan.html.markdown) |
| resource | `alicloud_hbr_nas_backup_plan` | DEPRECATED -> `alicloud_hbr_policy` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/hbr_nas_backup_plan.html.markdown) |
| resource | `alicloud_hbr_oss_backup_plan` | DEPRECATED -> `alicloud_hbr_policy` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/hbr_oss_backup_plan.html.markdown) |
| resource | `alicloud_hbr_ots_backup_plan` | DEPRECATED -> `alicloud_hbr_policy` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/hbr_ots_backup_plan.html.markdown) |
| resource | `alicloud_hbr_server_backup_plan` | DEPRECATED -> `alicloud_hbr_policy` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/hbr_server_backup_plan.html.markdown) |

## KMS

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_kms_keys` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/kms_keys.html.markdown) |

## Log Service (SLS)

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_log_alert_resource` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/log_alert_resource.html.markdown) |
| data source | `alicloud_log_projects` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/log_projects.html.markdown) |
| resource | `alicloud_log_oss_shipper` | DEPRECATED -> `alicloud_log_oss_export` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/log_oss_shipper.html.markdown) |

## Max Compute

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_max_compute_tunnel_quota_timer` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/max_compute_tunnel_quota_timer.html.markdown) |

## Message Service

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_mns_queues` | DEPRECATED -> `alicloud_message_service_queues` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/mns_queues.html.markdown) |
| data source | `alicloud_mns_service` | DEPRECATED -> `alicloud_message_service_service` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/mns_service.html.markdown) |
| data source | `alicloud_mns_topic_subscriptions` | DEPRECATED -> `alicloud_message_service_subscriptions` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/mns_topic_subscriptions.html.markdown) |
| data source | `alicloud_mns_topics` | DEPRECATED -> `alicloud_message_service_topics` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/mns_topics.html.markdown) |
| resource | `alicloud_mns_queue` | DEPRECATED -> `alicloud_message_service_queue` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/mns_queue.html.markdown) |
| resource | `alicloud_mns_topic` | DEPRECATED -> `alicloud_message_service_topic` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/mns_topic.html.markdown) |
| resource | `alicloud_mns_topic_subscription` | DEPRECATED -> `alicloud_message_service_subscription` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/mns_topic_subscription.html.markdown) |

## MongoDB

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_mongodb_serverless_instance` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/mongodb_serverless_instance.html.markdown) |

## OSS

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_oss_buckets` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/oss_buckets.html.markdown) |

## RAM

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_ram_policies` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/ram_policies.html.markdown) |
| data source | `alicloud_ram_role_policy_attachments` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/ram_role_policy_attachments.html.markdown) |
| data source | `alicloud_ram_roles` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/ram_roles.html.markdown) |
| resource | `alicloud_ram_group_membership` | DEPRECATED -> `alicloud_ram_user_group_attachment` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/ram_group_membership.html.markdown) |

## RDS

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_db_instance_classes` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/db_instance_classes.html.markdown) |
| data source | `alicloud_db_instances` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/db_instances.html.markdown) |
| data source | `alicloud_db_zones` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/db_zones.html.markdown) |
| resource | `alicloud_db_account` | DEPRECATED -> `alicloud_rds_account` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/db_account.html.markdown) |

## SCDN

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_scdn_domain` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/scdn_domain.html.markdown) |
| resource | `alicloud_scdn_domain_config` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/scdn_domain_config.html.markdown) |

## Service Catalog

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_service_catalog_product_as_end_users` | DEPRECATED -> `alicloud_service_catalog_end_user_products` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/service_catalog_product_as_end_users.html.markdown) |

## Tair (Redis OSS-Compatible) And Memcache (KVStore)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_kvstore_backup_policy` | DEPRECATED -> `alicloud_kvstore_instance` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/kvstore_backup_policy.html.markdown) |

## Time Series Database (TSDB)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_tsdb_instance` | DEPRECATED | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/tsdb_instance.html.markdown) |

## VPC

| type | name | status | doc |
| --- | --- | --- | --- |
| data source | `alicloud_vpcs` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/vpcs.html.markdown) |
| data source | `alicloud_vswitches` |  | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/d/vswitches.html.markdown) |
| resource | `alicloud_havip` | DEPRECATED -> `alicloud_vpc_ha_vip` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/havip.html.markdown) |
| resource | `alicloud_network_acl_attachment` | DEPRECATED -> `alicloud_network_acl` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/network_acl_attachment.html.markdown) |
| resource | `alicloud_network_acl_entries` | DEPRECATED -> `alicloud_network_acl` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/network_acl_entries.html.markdown) |

## Web Application Firewall(WAF)

| type | name | status | doc |
| --- | --- | --- | --- |
| resource | `alicloud_waf_domain` | DEPRECATED -> `alicloud_wafv3_domain` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/waf_domain.html.markdown) |
| resource | `alicloud_waf_instance` | DEPRECATED -> `alicloud_wafv3_instance` | [doc](https://github.com/aliyun/terraform-provider-alicloud/blob/master/website/docs/r/waf_instance.html.markdown) |
