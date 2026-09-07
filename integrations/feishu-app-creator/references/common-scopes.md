# 飞书开放平台常用权限 Scope 参考

按业务域分类的常用 scope key。`:readonly` 后缀表示只读，无后缀表示读写。完整列表见 https://open.feishu.cn/document/server-docs/application-scope/scope-list

## 通讯录 contact

| Scope key | 说明 |
|---|---|
| `contact:contact.base:readonly` | 获取通讯录基本信息 |
| `contact:user.base:readonly` | 获取用户基本信息 |
| `contact:user.email:readonly` | 获取用户邮箱 |
| `contact:user.phone:readonly` | 获取用户手机号 |
| `contact:user.employee_id:readonly` | 获取用户 user ID |
| `contact:user.employee_number:read` | 查看成员工号 |
| `contact:user.employee:readonly` | 获取用户雇佣信息 |
| `contact:department.base:readonly` | 获取部门基本信息 |
| `contact:department.organize:readonly` | 获取部门组织信息 |
| `contact:job_level:readonly` | 获取职级信息 |
| `contact:job_family:readonly` | 获取职务族信息 |
| `contact:user.id:readonly` | 通过手机号/邮箱获取用户 ID |

## 消息与群组 im

| Scope key | 说明 |
|---|---|
| `im:message` | 获取与发送单聊、群组消息（读写） |
| `im:message:readonly` | 读取单聊和群聊消息 |
| `im:message:send_as_bot` | 以应用身份发消息 |
| `im:message.p2p_msg:readonly` | 读取发给机器人的单聊消息 |
| `im:message.group_at_msg:readonly` | 读取群里 @机器人 的消息 |
| `im:message.group_at_msg.include_bot:readonly` | 读取群里 @机器人 的消息（含其他机器人） |
| `im:message:send_multi_users` | 批量给多个用户发消息 |
| `im:message:update` | 更新消息 |
| `im:message.pins:read` | 读取置顶消息 |
| `im:message.pins:write_only` | 置顶/取消置顶消息 |
| `im:message.reactions:read` | 读取消息表情回复 |
| `im:message.reactions:write_only` | 添加/删除消息表情回复 |
| `im:resource` | 上传/获取图片和文件资源 |
| `im:chat:create` | 创建群组 |
| `im:chat:read` | 读取群信息 |
| `im:chat:update` | 更新群信息 |
| `im:chat.members:bot_access` | 订阅机器人被加入/移出群事件 |

## 云文档 docx / docs / drive / wiki

| Scope key | 说明 |
|---|---|
| `docx:document` | 查看、评论、编辑和管理新版文档（读写） |
| `docx:document:readonly` | 查看新版文档 |
| `docx:document.block:convert` | 文本转文档块 |
| `docs:doc` | 查看、评论、编辑和管理旧版文档（读写） |
| `docs:doc:readonly` | 查看旧版文档 |
| `docs:document.comment:create` | 添加文档评论 |
| `docs:document.comment:read` | 读取文档评论 |
| `docs:document.comment:update` | 更新文档评论 |
| `docs:document.comment:delete` | 删除文档评论 |
| `drive:drive` | 查看、评论、编辑和管理云空间文件（读写） |
| `drive:drive:readonly` | 查看云空间文件 |
| `drive:drive.metadata:readonly` | 读取云空间文件元数据 |
| `wiki:wiki` | 查看、编辑和管理知识库（读写） |
| `wiki:wiki:readonly` | 查看知识库 |
| `wiki:node:read` | 查看知识空间节点信息 |

## 多维表格 bitable / base

| Scope key | 说明 |
|---|---|
| `bitable:app` | 查看、评论、编辑和管理多维表格（读写） |
| `bitable:app:readonly` | 查看、评论和导出多维表格 |
| `base:record:retrieve` | 查看记录 |
| `base:record:create` | 创建记录 |
| `base:record:update` | 更新记录 |
| `base:record:delete` | 删除记录 |
| `base:field:read` | 查看字段 |
| `base:field:create` | 添加字段 |
| `base:field:update` | 更新字段 |
| `base:field:delete` | 删除字段 |
| `base:table:read` | 查看数据表 |
| `base:table:create` | 创建数据表 |
| `base:table:update` | 更新数据表 |
| `base:table:delete` | 删除数据表 |

## 招聘 hire

| Scope key | 说明 |
|---|---|
| `hire:application` | 更新投递信息（读写） |
| `hire:application:readonly` | 获取投递信息 |
| `hire:job` | 更新职位信息（读写） |
| `hire:job:readonly` | 获取职位信息 |
| `hire:job_requirement` | 更新招聘需求信息（读写） |
| `hire:job_requirement:readonly` | 获取招聘需求信息 |
| `hire:job.composite_info:readonly` | 获取职位组合信息 |
| `hire:talent` | 更新人才信息（读写） |
| `hire:talent:readonly` | 获取人才信息 |
| `hire:interview` | 更新面试信息（读写） |
| `hire:interview:readonly` | 获取面试信息 |
| `hire:interviewer` | 更新面试官信息（读写） |
| `hire:interviewer:readonly` | 获取面试官信息 |
| `hire:referral:readonly` | 获取内推信息 |
| `hire:offer` | 更新 Offer 信息（读写） |
| `hire:offer:readonly` | 获取 Offer 信息 |
| `hire:location:readonly` | 获取地点信息 |

## 日历 calendar

| Scope key | 说明 |
|---|---|
| `calendar:calendar` | 查看、编辑和管理日历（读写） |
| `calendar:calendar:readonly` | 查看日历 |
| `calendar:calendar.event:create` | 创建日程 |
| `calendar:calendar.event:read` | 查看日程 |
| `calendar:calendar.event:update` | 更新日程 |
| `calendar:calendar.event:delete` | 删除日程 |
| `calendar:calendar.free_busy:read` | 查询空闲忙碌信息 |

## 审批 approval

| Scope key | 说明 |
|---|---|
| `approval:approval` | 查看、创建和管理审批定义/实例（读写） |
| `approval:approval:readonly` | 查看审批定义 |
| `approval:instance` | 获取和管理审批实例（读写） |
| `approval:instance:readonly` | 获取审批实例详情 |
| `approval:approval.list:readonly` | 查询实例列表 |

## 任务 task

| Scope key | 说明 |
|---|---|
| `task:task` | 查看、创建和管理任务（读写） |
| `task:task:read` | 查看任务 |

## 考勤 attendance

| Scope key | 说明 |
|---|---|
| `attendance:task` | 查看和管理考勤任务（读写） |
| `attendance:task:read` | 查看考勤任务 |
| `attendance:record` | 查看和管理打卡记录（读写） |
| `attendance:record:read` | 查看打卡记录 |

## 应用管理 application

| Scope key | 说明 |
|---|---|
| `application:application:self_manage` | 管理应用自身资源 |
| `application:app:read` | 获取应用信息 |
| `application:bot.basic_info:read` | 获取机器人基本信息 |
| `application:bot.menu:write` | 创建/更新/删除机器人菜单 |
| `application:app_slash_command:read` | 查看快捷指令 |
| `application:app_slash_command:write` | 编辑快捷指令 |

## 企业信息 tenant

| Scope key | 说明 |
|---|---|
| `tenant:tenant:readonly` | 获取企业信息 |

## 卡片 cardkit

| Scope key | 说明 |
|---|---|
| `cardkit:card:read` | 读取卡片数据 |
| `cardkit:card:write` | 创建和更新卡片 |

## 用户身份权限 user scopes

| Scope key | 说明 |
|---|---|
| `offline_access` | 持续访问授权数据（获取 refresh_token） |

## 常用事件 events

| Event key | 说明 |
|---|---|
| `im.message.receive_v1` | 接收消息 |
| `im.message.reaction.created_v1` | 消息被添加表情回复 |
| `im.message.reaction.deleted_v1` | 消息表情回复被删除 |
| `im.chat.member.bot.added_v1` | 机器人被加入群聊 |
| `im.chat.member.bot.deleted_v1` | 机器人被移出群聊 |
| `drive.notice.comment_add_v1` | 文档新增评论或回复 |
| `calendar.calendar.event.changed_v4` | 日程变更 |
| `contact.user.created_v3` | 用户创建 |
| `contact.user.deleted_v3` | 用户删除 |
| `contact.department.created_v3` | 部门创建 |
| `contact.department.deleted_v3` | 部门删除 |

## 常用回调 callbacks

| Callback key | 说明 |
|---|---|
| `card.action.trigger` | 卡片交互回调 |
