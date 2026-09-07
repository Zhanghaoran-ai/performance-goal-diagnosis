#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绩效目标拆解诊断 - 统一入口脚本
一站式完成数据采集 + 诊断 + 输出，支持多种输入方式和输出格式

使用方式：
  # 通过部门 ID 诊断
  python3 scripts/diagnose.py --department-id od-xxxxx

  # 通过部门名称诊断（自动搜索）
  python3 scripts/diagnose.py --department-name "客户成功中心"

  # 通过用户列表诊断
  python3 scripts/diagnose.py --user-ids "ou_xxx,ou_yyy"

  # 诊断我的团队
  python3 scripts/diagnose.py --my-team

  # 从已有数据文件诊断（跳过采集）
  python3 scripts/diagnose.py --input goal_data.json

  # 指定输出格式
  python3 scripts/diagnose.py --department-name "团队名" --format markdown

  # 使用缓存
  python3 scripts/diagnose.py --department-name "团队名" --use-cache

  # 指定行业指标库
  python3 scripts/diagnose.py --input data.json --industry-metrics ./metrics
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 添加脚本目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from feishu_performance_adapter import FeishuPerformanceCollector, PerformanceAPIError, parse_variables
except ImportError:  # 由运行时错误明确暴露，而非静默声称支持
    FeishuPerformanceCollector = None
    PerformanceAPIError = RuntimeError


# 用户反馈入口的 HTML 片段
FEEDBACK_SECTION_HTML = """
    <!-- 用户反馈入口 -->
    <div style="margin-top: 40px; padding: 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px; color: white;">
        <h2 style="margin: 0 0 16px 0; font-size: 20px;">📝 指标不准？欢迎反馈</h2>
        <p style="margin: 8px 0; opacity: 0.95;">如发现本报告中的行业基准指标不准或不对，您的反馈将帮助我们持续优化！</p>
        <div style="margin-top: 16px; display: flex; gap: 12px; flex-wrap: wrap;">
            <button onclick="alert('反馈方式：\n📧 请联系指标库维护者\n💬 格式：指标名称 + 问题描述 + 建议值\n⏱️ 3个工作日内回复')" 
                    style="padding: 10px 20px; background: white; color: #667eea; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 14px;">
                🔔 反馈指标不准
            </button>
            <button onclick="alert('感谢您的反馈！\n请详细描述：\n1. 哪个指标有问题\n2. 具体问题是什么\n3. 您认为正确的值应该是多少')" 
                    style="padding: 10px 20px; background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.5); border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 14px;">
                💡 提供建议值
            </button>
        </div>
        <p style="margin: 16px 0 0 0; font-size: 12px; opacity: 0.8;">
            同一指标收到 ≥3 个类似反馈将触发即时更新 | 响应时间：3个工作日
        </p>
    </div>
    
    <div style="margin-top: 24px; text-align: center; color: #9ca3af; font-size: 12px;">
        本报告由绩效目标拆解诊断工具 v2.7 自动生成 | 行业指标库版本：v2.6.0（2026-09-04）
    </div>
"""


class GoalDiagnosisTool:
    """绩效目标拆解诊断工具 - 统一入口"""

    def __init__(self):
        self.args = None
        self.data = None
        self.result = None
        self.collector = None
        self.diagnoser = None

    def parse_args(self):
        """解析命令行参数"""
        parser = argparse.ArgumentParser(
            description='绩效目标拆解诊断工具 - 一站式数据采集 + 诊断 + 输出',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
示例：
  # 通过部门名称诊断（最常用）
  python3 diagnose.py --department-name "客户成功中心"

  # 通过部门 ID 诊断
  python3 diagnose.py --department-id od-xxxxx

  # 从已有数据文件诊断
  python3 diagnose.py --input goal_data.json

  # 输出 Markdown 格式
  python3 diagnose.py --department-name "团队名" --format markdown

  # 使用缓存（更快）
  python3 diagnose.py --department-name "团队名" --use-cache
            """
        )

        # 输入方式（选择一种主数据来源；关系决策为附加输入）
        input_group = parser.add_argument_group('输入方式（选择一种主数据来源）')
        input_group.add_argument('--department-id', type=str, help='部门 ID（最准确）')
        input_group.add_argument('--department-name', type=str, help='部门名称（自动搜索）')
        input_group.add_argument('--user-ids', type=str, help='用户 ID 列表，逗号分隔')
        input_group.add_argument('--my-team', action='store_true', help='诊断我的团队（降级方案）')
        input_group.add_argument('--input', '-i', type=str, help='已有数据文件路径（跳过采集）')
        input_group.add_argument('--feishu-performance-config', type=str,
                                 help='飞书绩效 API 配置 JSON；接口、权限和字段映射由用户提供')
        input_group.add_argument('--api-var', action='append', default=[], metavar='KEY=VALUE',
                                 help='接口路径/请求参数模板变量，可重复提供；禁止用于传递密钥')
        input_group.add_argument('--relation-decisions', type=str,
                                 help='由 HTML 报告导出的 indicator-relation-decisions.json，人工决策优先于语义推断')

        # 输出选项
        output_group = parser.add_argument_group('输出选项')
        output_group.add_argument('--output', '-o', type=str,
                                  default='diagnosis_result.json',
                                  help='输出文件路径（默认 diagnosis_result.json）')
        output_group.add_argument('--format', '-f', type=str,
                                  choices=['json', 'text', 'markdown', 'html'],
                                  default='json',
                                  help='输出格式：json/text/markdown/html（默认 json）')
        output_group.add_argument('--legacy-format', action='store_true',
                                  help='使用旧版输出格式（默认使用标准输出框架，6 页面结构）')
        output_group.add_argument('--tree-style', type=str,
                                  choices=['enhanced', 'legacy'],
                                  default='enhanced',
                                  help='拆解视图样式：enhanced（默认；含独立指标拆解树 + 层级强化目标树）/ legacy（旧版目标树）')

        # 诊断选项
        diag_group = parser.add_argument_group('诊断选项')
        diag_group.add_argument('--industry-metrics', type=str,
                                help='行业指标库文件夹路径（可选，默认使用内置指标库）')
        diag_group.add_argument('--industry', type=str,
                                help='指定行业（如：制造业、汽车行业、新能源行业等），不指定则自动识别')
        diag_group.add_argument('--import-template', type=str,
                                metavar='MARKDOWN',
                                help='v2.5 新增：先应用 industry-performance-template 技能产出绩效方案 Markdown，'
                                     '再传入本参数自动转换为行业指标库并完成对标诊断（一键完成"模板→诊断"闭环）')
        diag_group.add_argument('--no-industry-metrics', action='store_true',
                                help='禁用行业指标库（不加载内置指标库）')
        diag_group.add_argument('--severity-threshold', type=str,
                                choices=['high', 'medium', 'low'],
                                default='low',
                                help='只显示指定严重度及以上的问题（默认 low，显示全部）')

        # 缓存选项
        cache_group = parser.add_argument_group('缓存选项')
        cache_group.add_argument('--use-cache', action='store_true',
                                 help='使用缓存数据（如果有）')
        cache_group.add_argument('--cache-dir', type=str,
                                 default='./.cache',
                                 help='缓存目录（默认 ./.cache）')
        cache_group.add_argument('--force-refresh', action='store_true',
                                 help='强制刷新缓存，忽略已有缓存')
        cache_group.add_argument('--cache-ttl', type=int,
                                 default=86400,
                                 help='缓存过期时间（秒），默认 86400（24小时）')

        # 其他选项
        other_group = parser.add_argument_group('其他选项')
        other_group.add_argument('--department-id-type', type=str,
                                 choices=['open_department_id', 'department_id'],
                                 default='open_department_id',
                                 help='部门 ID 类型（默认 open_department_id）')
        other_group.add_argument('--verbose', '-v', action='store_true',
                                 help='详细输出模式')
        other_group.add_argument('--validate', action='store_true',
                                 help='只校验输入数据，不运行诊断')

        self.args = parser.parse_args()
        return self.args

    def validate_input(self):
        """校验输入参数"""
        # 检查是否指定了输入方式
        input_methods = [
            self.args.department_id,
            self.args.department_name,
            self.args.user_ids,
            self.args.my_team,
            self.args.input,
            self.args.feishu_performance_config,
        ]
        if not any(input_methods):
            print("❌ 请指定输入方式")
            print("   可选：--department-id / --department-name / --user-ids / --my-team / --input / --feishu-performance-config")
            sys.exit(1)

        # 检查是否指定了多种输入方式
        specified = [m for m in input_methods if m]
        if len(specified) > 1:
            print("❌ 只能指定一种输入方式")
            sys.exit(1)

        # 如果是文件输入，检查文件是否存在
        if self.args.input:
            if not os.path.exists(self.args.input):
                print(f"❌ 输入文件不存在：{self.args.input}")
                sys.exit(1)
        if self.args.feishu_performance_config and not os.path.exists(self.args.feishu_performance_config):
            print(f"❌ 飞书绩效接口配置不存在：{self.args.feishu_performance_config}")
            sys.exit(1)
        if self.args.relation_decisions and not os.path.exists(self.args.relation_decisions):
            print(f"❌ 关系决策文件不存在：{self.args.relation_decisions}")
            sys.exit(1)

        return True

    def get_cache_key(self):
        """生成缓存键"""
        if self.args.department_id:
            return f"dept_{self.args.department_id}"
        elif self.args.department_name:
            return f"dept_name_{self.args.department_name}"
        elif self.args.user_ids:
            return f"users_{hash(self.args.user_ids)}"
        elif self.args.my_team:
            return "my_team"
        else:
            return None

    def get_cache_path(self):
        """获取缓存文件路径"""
        cache_key = self.get_cache_key()
        if not cache_key:
            return None
        cache_dir = Path(self.args.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{cache_key}.json"

    def check_cache(self):
        """检查缓存是否有效"""
        cache_path = self.get_cache_path()
        if not cache_path or not cache_path.exists():
            return False

        # 检查是否强制刷新
        if self.args.force_refresh:
            if self.args.verbose:
                print("🔄 强制刷新缓存")
            return False

        # 检查缓存是否过期
        mtime = cache_path.stat().st_mtime
        age = time.time() - mtime
        if age > self.args.cache_ttl:
            if self.args.verbose:
                print(f"⏰ 缓存已过期（{int(age/3600)}小时）")
            return False

        if self.args.verbose:
            print(f"✅ 缓存有效（{int(age/3600)}小时）")
        return True

    def load_cache(self):
        """从缓存加载数据"""
        cache_path = self.get_cache_path()
        if not cache_path:
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if self.args.verbose:
                print(f"📦 从缓存加载数据：{cache_path}")
            return data
        except Exception as e:
            print(f"⚠️  缓存加载失败：{e}")
            return None

    def save_cache(self, data):
        """保存数据到缓存"""
        cache_path = self.get_cache_path()
        if not cache_path:
            return

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if self.args.verbose:
                print(f"💾 数据已缓存：{cache_path}")
        except Exception as e:
            if self.args.verbose:
                print(f"⚠️  缓存保存失败：{e}")

    def _attach_relation_decisions(self, data):
        """把 HTML 导出的人工裁决附到标准输入；不覆盖原始显式关系。"""
        path = getattr(self.args, 'relation_decisions', None)
        if not path:
            return data
        with open(path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        decisions = payload.get('decisions', payload) if isinstance(payload, dict) else payload
        if not isinstance(decisions, list):
            raise ValueError('关系决策文件应包含 decisions 数组')
        data['indicator_relation_decisions'] = decisions
        print(f"  已加载人工关系决策：{len(decisions)} 条")
        return data

    def collect_data(self):
        """采集数据"""
        print("📊 开始数据采集...")

        # 如果是从文件输入，直接加载
        if self.args.input:
            print(f"  方式：从文件加载（{self.args.input}）")
            with open(self.args.input, 'r', encoding='utf-8') as f:
                result = json.load(f)
            self.data = self._attach_relation_decisions(result)
            meta = result.get('meta', {})
            print(f"✅ 数据加载完成")
            print(f"   总人数：{meta.get('total_users', 0)}")
            print(f"   有 OKR 的人数：{meta.get('users_with_okr', 0)}")
            print(f"   目标总数：{meta.get('total_goals', 0)}")
            print(f"   权限级别：Level {meta.get('permission_level', 3)}")

            # 打印警告
            warnings = meta.get('warnings', [])
            if warnings:
                print(f"   ⚠️  警告（{len(warnings)} 条）：")
                for w in warnings[:3]:
                    print(f"      - {w}")
                if len(warnings) > 3:
                    print(f"      ... 还有 {len(warnings) - 3} 条")

            return result

        # 用户提供绩效接口配置：配置驱动采集，不猜测官方路径或字段
        if self.args.feishu_performance_config:
            if FeishuPerformanceCollector is None:
                print("❌ 无法加载飞书绩效 API 适配器")
                sys.exit(1)
            print(f"  方式：飞书绩效 API 配置（{self.args.feishu_performance_config}）")
            try:
                variables = parse_variables(self.args.api_var)
                collector = FeishuPerformanceCollector.from_file(
                    self.args.feishu_performance_config, variables=variables
                )
                result = collector.collect()
                self.collector = collector
                self.data = self._attach_relation_decisions(result)
            except (PerformanceAPIError, ValueError, OSError, json.JSONDecodeError) as exc:
                print(f"❌ 飞书绩效数据采集失败：{exc}")
                sys.exit(1)
            meta = result.get('meta', {})
            print("✅ 飞书绩效数据采集并标准化完成")
            print(f"   总人数：{meta.get('total_users', 0)}")
            print(f"   目标总数：{meta.get('total_goals', 0)}")
            if meta.get('warnings'):
                print(f"   ⚠️  映射警告：{len(meta['warnings'])} 条")
            return result

        # 检查缓存
        if self.args.use_cache and self.check_cache():
            self.data = self.load_cache()
            if self.data:
                print(f"✅ 从缓存加载数据（{self.data.get('meta', {}).get('total_users', 0)} 人）")
                return self.data

        # 导入数据采集模块
        try:
            from collect_data import DataCollector
        except ImportError as e:
            print(f"❌ 无法加载数据采集模块：{e}")
            print("   提示：如果只是从文件诊断，请使用 --input 参数")
            sys.exit(1)

        collector = DataCollector()
        self.collector = collector

        # 根据输入方式采集数据
        if self.args.department_id:
            print(f"  方式：部门 ID（{self.args.department_id}）")
            result = collector.collect_by_department_id(
                self.args.department_id,
                dept_id_type=self.args.department_id_type
            )
        elif self.args.department_name:
            print(f"  方式：部门名称（{self.args.department_name}）")
            result = collector.collect_by_department_name(self.args.department_name)
        elif self.args.user_ids:
            user_ids = [uid.strip() for uid in self.args.user_ids.split(',')]
            print(f"  方式：用户列表（{len(user_ids)} 人）")
            result = collector.collect_by_user_ids(user_ids)
        elif self.args.my_team:
            print("  方式：我的团队")
            result = collector.collect_my_team()
        else:
            # 从文件加载
            print(f"  方式：从文件加载（{self.args.input}）")
            with open(self.args.input, 'r', encoding='utf-8') as f:
                result = json.load(f)

        self.data = result

        # 保存缓存（如果是自动采集的）
        if self.args.use_cache and not self.args.input:
            self.save_cache(result)

        # 打印统计
        meta = result.get('meta', {})
        print(f"✅ 数据采集完成")
        print(f"   总人数：{meta.get('total_users', 0)}")
        print(f"   有 OKR 的人数：{meta.get('users_with_okr', 0)}")
        print(f"   目标总数：{meta.get('total_goals', 0)}")
        print(f"   权限级别：Level {meta.get('permission_level', 3)}")

        # 打印警告
        warnings = meta.get('warnings', [])
        if warnings:
            print(f"   ⚠️  警告（{len(warnings)} 条）：")
            for w in warnings[:3]:
                print(f"      - {w}")
            if len(warnings) > 3:
                print(f"      ... 还有 {len(warnings) - 3} 条")

        return result

    def validate_data(self):
        """校验数据格式"""
        print("\n🔍 校验数据格式...")

        if not self.data:
            print("❌ 没有数据")
            return False

        errors = []
        warnings = []

        # 检查必填字段
        if 'meta' not in self.data:
            errors.append("缺少 meta 字段")
        if 'goals' not in self.data:
            errors.append("缺少 goals 字段")
        if 'users' not in self.data:
            errors.append("缺少 users 字段")

        if errors:
            print(f"❌ 数据校验失败（{len(errors)} 个错误）")
            for e in errors:
                print(f"   - {e}")
            return False

        # 检查目标数据
        goals = self.data.get('goals', [])
        for i, goal in enumerate(goals):
            if 'goal_id' not in goal:
                errors.append(f"目标 #{i} 缺少 goal_id")
            if 'title' not in goal:
                errors.append(f"目标 #{i} 缺少 title")
            if 'owner_id' not in goal:
                warnings.append(f"目标 #{i}（{goal.get('title', '未知')}）缺少 owner_id")
            if 'progress' in goal:
                p = goal['progress']
                if p < 0 or p > 1:
                    warnings.append(f"目标 #{i} 的 progress={p}，超出 0-1 范围")

        # 检查人员数据
        users = self.data.get('users', [])
        for i, user in enumerate(users):
            if 'user_id' not in user:
                errors.append(f"用户 #{i} 缺少 user_id")
            if 'name' not in user:
                warnings.append(f"用户 #{i} 缺少 name")

        if errors:
            print(f"❌ 数据校验失败（{len(errors)} 个错误）")
            for e in errors:
                print(f"   - {e}")
            return False

        if warnings:
            print(f"⚠️  数据校验有警告（{len(warnings)} 条）")
            for w in warnings[:5]:
                print(f"   - {w}")
            if len(warnings) > 5:
                print(f"   ... 还有 {len(warnings) - 5} 条")
        else:
            print("✅ 数据校验通过")

        return True

    def run_diagnosis(self):
        """运行诊断"""
        print("\n🔬 开始多维度诊断...")

        # 导入诊断模块
        try:
            from diagnose_goals import GoalDiagnoser
        except ImportError:
            print("❌ 无法加载诊断模块")
            sys.exit(1)

        # v2.5：--import-template 一键完成"模板技能输出→行业指标库→诊断"闭环
        if getattr(self.args, 'import_template', None):
            try:
                from import_template_output import (
                    parse_markdown_table, build_industry_library, render_layer_md,
                )
                template_path = Path(self.args.import_template)
                if not template_path.exists():
                    print(f"  ❌ 模板文件不存在：{template_path}")
                    sys.exit(1)
                industry_name = getattr(self.args, 'industry', None) or '通用行业'
                # 输出到默认指标库目录下的 <行业名>/
                base_out = Path(getattr(self.args, 'industry_metrics', None)
                                or str(Path.cwd() / 'industry_metrics'))
                out_dir = base_out / industry_name
                md_text = template_path.read_text(encoding='utf-8')
                tables = parse_markdown_table(md_text)
                layers = build_industry_library(tables, industry_name)
                total = sum(len(v) for v in layers.values())
                if total == 0:
                    print("  ❌ 模板中未解析到指标，请确认第4章「指标&目标范例明细」表格式")
                    sys.exit(1)
                out_dir.mkdir(parents=True, exist_ok=True)
                layer_names = {'战略层': '战略层', '管理层': '管理层', '执行层': '执行层'}
                for lv in ['战略层', '管理层', '执行层']:
                    if layers[lv]:
                        content = render_layer_md(layer_names[lv], layers[lv],
                                                  industry_name,
                                                  f'{industry_name}绩效模板（{template_path.name}）')
                        (out_dir / f"{lv}指标.md").write_text(content, encoding='utf-8')
                print(f"  ✅ 模板→行业指标库：{total} 个指标 → {out_dir}")
                self.args.industry_metrics = str(base_out)
                industry_metrics = str(base_out)
            except ImportError:
                print("  ⚠️  import_template_output 模块加载失败，跳过模板导入")
                industry_metrics = None
            except Exception as e:
                print(f"  ⚠️  模板导入失败：{e}")
                industry_metrics = None
            else:
                # 进入正常行业库加载逻辑
                pass

        # 加载行业指标库
        industry_metrics = None
        if self.args.industry_metrics:
            metrics_path = Path(self.args.industry_metrics)
            if metrics_path.exists():
                industry_metrics = str(metrics_path)
                print(f"  行业指标库：{metrics_path}")
            else:
                print(f"  ⚠️  行业指标库路径不存在：{metrics_path}")

        # 创建诊断器（v2.2：默认自动加载内置指标库）
        auto_load = not getattr(self.args, 'no_industry_metrics', False)
        diagnoser = GoalDiagnoser(
            industry_metrics_path=industry_metrics,
            severity_threshold=self.args.severity_threshold,
            industry=getattr(self.args, 'industry', None),
            auto_load_metrics=auto_load
        )
        self.diagnoser = diagnoser

        # 运行诊断
        result = diagnoser.run_all_diagnoses(self.data)
        self.result = result

        # 打印统计
        summary = result.get('summary', {})
        print(f"✅ 诊断完成")
        print(f"   健康度：{summary.get('health_score', 0)} / 100（{summary.get('health_level', '未知')}）")
        print(f"   问题总数：{summary.get('total_issues', 0)}")
        print(f"     高严重度：{summary.get('high_count', 0)}")
        print(f"     中严重度：{summary.get('medium_count', 0)}")
        print(f"     低严重度：{summary.get('low_count', 0)}")

        return result

    def format_output(self):
        """格式化输出"""
        fmt = self.args.format

        if fmt == 'json':
            return self._format_json()
        elif fmt == 'text':
            return self._format_text()
        elif fmt == 'markdown':
            return self._format_markdown()
        elif fmt == 'html':
            return self._format_html()
        else:
            return self._format_json()

    def _format_json(self):
        """JSON 格式"""
        return json.dumps(self.result, ensure_ascii=False, indent=2)

    def _format_text(self):
        """纯文本格式"""
        if self.diagnoser:
            return self.diagnoser.generate_text_report(self.result)
        else:
            return json.dumps(self.result, ensure_ascii=False, indent=2)

    def _format_markdown(self):
        """Markdown 格式"""
        # 标准输出框架（默认启用，v2.6）
        if not getattr(self.args, 'legacy_format', False):
            try:
                from standard_report import StandardReportGenerator
                generator = StandardReportGenerator(self.result, self.data,
                                                    tree_style=getattr(self.args, 'tree_style', 'enhanced'))
                return generator.generate_markdown()
            except ImportError as e:
                print(f"⚠️  标准报告模块加载失败，使用默认格式：{e}")

        summary = self.result.get('summary', {})
        issues = self.result.get('issues', [])
        suggestions = self.result.get('suggestions', [])
        goals = self.data.get('goals', [])
        users = self.data.get('users', [])

        # 健康度等级和 emoji
        score = summary.get('health_score', 0)
        level = summary.get('health_level', '')
        if score >= 90:
            emoji = '🟢'
        elif score >= 70:
            emoji = '🔵'
        elif score >= 50:
            emoji = '🟡'
        else:
            emoji = '🔴'

        md = []
        md.append(f"# 绩效目标拆解诊断报告")
        md.append("")
        md.append(f"**诊断时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        md.append(f"**目标总数**：{len(goals)} 个")
        md.append(f"**参与人数**：{len(users)} 人")
        md.append("")

        # 健康度概览
        md.append("## 📊 健康度概览")
        md.append("")
        md.append(f"### 综合健康度：{emoji} {score} / 100（{level}）")
        md.append("")
        md.append("| 指标 | 数值 |")
        md.append("|------|------|")
        md.append(f"| 目标总数 | {summary.get('total_goals', 0)} |")
        md.append(f"| 问题总数 | {summary.get('total_issues', 0)} |")
        md.append(f"| 高严重度 | {summary.get('high_count', 0)} |")
        md.append(f"| 中严重度 | {summary.get('medium_count', 0)} |")
        md.append(f"| 低严重度 | {summary.get('low_count', 0)} |")
        md.append("")

        # 各维度问题分布
        md.append("## 📈 各维度问题分布")
        md.append("")
        by_dimension = summary.get('by_dimension', {})
        if by_dimension:
            md.append("| 诊断维度 | 问题数 |")
            md.append("|----------|--------|")
            for dim, count in by_dimension.items():
                md.append(f"| {dim} | {count} |")
            md.append("")

        # 问题列表
        md.append("## ⚠️ 问题清单")
        md.append("")

        # 按严重度分组
        high_issues = [i for i in issues if i.get('severity') == 'high']
        medium_issues = [i for i in issues if i.get('severity') == 'medium']
        low_issues = [i for i in issues if i.get('severity') == 'low']

        if high_issues:
            md.append("### 🔴 高严重度")
            md.append("")
            for i, issue in enumerate(high_issues, 1):
                md.append(f"**{i}. [{issue.get('dimension', '')}] {issue.get('title', '')}**")
                md.append("")
                md.append(f"- 目标：{issue.get('goal_title', 'N/A')}")
                md.append(f"- 描述：{issue.get('description', '')}")
                if issue.get('evidence'):
                    md.append(f"- 证据：{issue.get('evidence', '')}")
                md.append("")

        if medium_issues:
            md.append("### 🟡 中严重度")
            md.append("")
            for i, issue in enumerate(medium_issues, 1):
                md.append(f"**{i}. [{issue.get('dimension', '')}] {issue.get('title', '')}**")
                md.append("")
                md.append(f"- 目标：{issue.get('goal_title', 'N/A')}")
                md.append(f"- 描述：{issue.get('description', '')}")
                if issue.get('evidence'):
                    md.append(f"- 证据：{issue.get('evidence', '')}")
                md.append("")

        if low_issues:
            md.append("### 🔵 低严重度")
            md.append("")
            for i, issue in enumerate(low_issues, 1):
                md.append(f"**{i}. [{issue.get('dimension', '')}] {issue.get('title', '')}**")
                md.append("")
                md.append(f"- 目标：{issue.get('goal_title', 'N/A')}")
                md.append(f"- 描述：{issue.get('description', '')}")
                if issue.get('evidence'):
                    md.append(f"- 证据：{issue.get('evidence', '')}")
                md.append("")

        # 优化建议
        if suggestions:
            md.append("## 💡 优化建议")
            md.append("")

            p0_suggestions = [s for s in suggestions if s.get('priority') == 'P0']
            p1_suggestions = [s for s in suggestions if s.get('priority') == 'P1']
            p2_suggestions = [s for s in suggestions if s.get('priority') == 'P2']

            if p0_suggestions:
                md.append("### 🚨 P0（立即处理）")
                md.append("")
                for i, s in enumerate(p0_suggestions, 1):
                    md.append(f"**{i}. {s.get('title', '')}**")
                    md.append("")
                    md.append(f"- 责任人：{s.get('owner', '待定')}")
                    md.append(f"- 建议：{s.get('description', '')}")
                    md.append("")

            if p1_suggestions:
                md.append("### ⚡ P1（尽快处理）")
                md.append("")
                for i, s in enumerate(p1_suggestions, 1):
                    md.append(f"**{i}. {s.get('title', '')}**")
                    md.append("")
                    md.append(f"- 责任人：{s.get('owner', '待定')}")
                    md.append(f"- 建议：{s.get('description', '')}")
                    md.append("")

            if p2_suggestions:
                md.append("### 📌 P2（有空再改）")
                md.append("")
                for i, s in enumerate(p2_suggestions, 1):
                    md.append(f"**{i}. {s.get('title', '')}**")
                    md.append("")
                    md.append(f"- 责任人：{s.get('owner', '待定')}")
                    md.append(f"- 建议：{s.get('description', '')}")
                    md.append("")

        # 附录：目标拆解树
        md.append("## 📋 附录：目标拆解树")
        md.append("")
        md.append("```")
        md.append(self._build_goal_tree_text())
        md.append("```")
        md.append("")

        # 人员列表
        md.append("## 👥 附录：人员列表")
        md.append("")
        md.append("| 姓名 | 层级 | 部门 | 目标数 |")
        md.append("|------|------|------|--------|")
        for user in users:
            user_goals = [g for g in goals if g.get('owner_id') == user.get('user_id')]
            md.append(f"| {user.get('name', '')} | {user.get('level', '')} | {user.get('department', '')} | {len(user_goals)} |")
        md.append("")

        # 添加用户反馈入口
        md.append("")
        md.append("---")
        md.append("")
        md.append("## 📝 用户反馈")
        md.append("")
        md.append("> 如发现本报告中的**行业基准指标不准或不对**，欢迎反馈：")
        md.append("> ")
        md.append("> - 📧 反馈邮箱：请联系指标库维护者")
        md.append("> - 💬 反馈格式：指标名称 + 问题描述 + 建议值/正确值")
        md.append("> - ⏱️ 响应时间：3个工作日内回复")
        md.append("> ")
        md.append("> 您的反馈将帮助我们持续优化行业指标库！同一指标收到 ≥3 个类似反馈将触发即时更新。")
        md.append("")
        md.append("---")
        md.append("")
        md.append("*本报告由绩效目标拆解诊断工具 v2.5 自动生成 | 行业指标库版本：v2.5.0（2026-08-11）*")
        return "\n".join(md)

    def _build_goal_tree_text(self):
        """构建目标树文本"""
        goals = self.data.get('goals', [])
        users = self.data.get('users', [])

        # 按层级分组
        levels = {}
        for goal in goals:
            level = goal.get('level', 'L?')
            if level not in levels:
                levels[level] = []
            levels[level].append(goal)

        lines = []
        for level in sorted(levels.keys()):
            level_goals = levels[level]
            lines.append(f"\n{level}（{len(level_goals)} 个目标）")
            lines.append("-" * 40)
            for goal in level_goals:
                owner = goal.get('owner_name', '未知')
                title = goal.get('title', '无标题')
                progress = int(goal.get('progress', 0) * 100)
                lines.append(f"  [{owner}] {title} ({progress}%)")

        # 添加用户反馈入口
        lines.append("")
        lines.append("=" * 60)
        lines.append("📝 用户反馈")
        lines.append("=" * 60)
        lines.append("如发现本报告中的行业基准指标不准或不对，欢迎反馈：")
        lines.append("")
        lines.append("  📧 反馈邮箱：请联系指标库维护者")
        lines.append("  💬 反馈格式：指标名称 + 问题描述 + 建议值/正确值")
        lines.append("  ⏱️ 响应时间：3个工作日内回复")
        lines.append("")
        lines.append("您的反馈将帮助我们持续优化行业指标库！")
        lines.append("同一指标收到 ≥3 个类似反馈将触发即时更新。")
        lines.append("")
        lines.append("=" * 60)
        lines.append("本报告由绩效目标拆解诊断工具 v2.7 自动生成")
        lines.append("行业指标库版本：v2.6.0（2026-09-04）")
        lines.append("=" * 60)
        return "\n".join(lines)

    def _format_html(self):
        """HTML 格式（简单版）"""
        # 标准输出框架（默认启用，v2.6）
        if not getattr(self.args, 'legacy_format', False):
            try:
                from standard_report import StandardReportGenerator
                generator = StandardReportGenerator(self.result, self.data,
                                                    tree_style=getattr(self.args, 'tree_style', 'enhanced'))
                return generator.generate_html()
            except ImportError as e:
                print(f"⚠️  标准报告模块加载失败，使用默认格式：{e}")

        summary = self.result.get('summary', {})
        issues = self.result.get('issues', [])
        suggestions = self.result.get('suggestions', [])
        goals = self.data.get('goals', [])
        users = self.data.get('users', [])

        score = summary.get('health_score', 0)
        level = summary.get('health_level', '')

        # 健康度颜色
        if score >= 90:
            color = '#10b981'  # green
        elif score >= 70:
            color = '#3b82f6'  # blue
        elif score >= 50:
            color = '#f59e0b'  # yellow
        else:
            color = '#ef4444'  # red

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绩效目标拆解诊断报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}
        .header p {{
            opacity: 0.9;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .card h2 {{
            font-size: 1.5rem;
            margin-bottom: 20px;
            color: #1f2937;
        }}
        .health-score {{
            text-align: center;
            padding: 40px 0;
        }}
        .score-circle {{
            width: 200px;
            height: 200px;
            border-radius: 50%;
            background: conic-gradient({color} {score}%, #e5e7eb {score}%);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 20px;
            position: relative;
        }}
        .score-inner {{
            width: 160px;
            height: 160px;
            border-radius: 50%;
            background: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .score-number {{
            font-size: 3rem;
            font-weight: bold;
            color: {color};
        }}
        .score-label {{
            font-size: 1rem;
            color: #6b7280;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 20px;
        }}
        .stat-item {{
            text-align: center;
            padding: 20px;
            background: #f9fafb;
            border-radius: 12px;
        }}
        .stat-number {{
            font-size: 2rem;
            font-weight: bold;
            color: #1f2937;
        }}
        .stat-label {{
            font-size: 0.9rem;
            color: #6b7280;
            margin-top: 4px;
        }}
        .high {{ color: #ef4444; }}
        .medium {{ color: #f59e0b; }}
        .low {{ color: #3b82f6; }}
        .issue-list {{
            list-style: none;
        }}
        .issue-item {{
            padding: 16px;
            border-radius: 12px;
            margin-bottom: 12px;
            border-left: 4px solid;
        }}
        .issue-item.high {{
            background: #fef2f2;
            border-left-color: #ef4444;
        }}
        .issue-item.medium {{
            background: #fffbeb;
            border-left-color: #f59e0b;
        }}
        .issue-item.low {{
            background: #eff6ff;
            border-left-color: #3b82f6;
        }}
        .issue-title {{
            font-weight: 600;
            margin-bottom: 8px;
            color: #1f2937;
        }}
        .issue-meta {{
            font-size: 0.85rem;
            color: #6b7280;
            margin-bottom: 8px;
        }}
        .issue-desc {{
            font-size: 0.9rem;
            color: #4b5563;
        }}
        .suggestion-item {{
            padding: 16px;
            background: #f0fdf4;
            border-radius: 12px;
            margin-bottom: 12px;
            border-left: 4px solid #10b981;
        }}
        .footer {{
            text-align: center;
            color: white;
            opacity: 0.7;
            margin-top: 30px;
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 绩效目标拆解诊断报告</h1>
            <p>诊断时间：{time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="card">
            <h2>健康度概览</h2>
            <div class="health-score">
                <div class="score-circle">
                    <div class="score-inner">
                        <div class="score-number">{score}</div>
                        <div class="score-label">{level}</div>
                    </div>
                </div>
            </div>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-number">{summary.get('total_goals', 0)}</div>
                    <div class="stat-label">目标总数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{summary.get('total_issues', 0)}</div>
                    <div class="stat-label">问题总数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number high">{summary.get('high_count', 0)}</div>
                    <div class="stat-label">高严重度</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number medium">{summary.get('medium_count', 0)}</div>
                    <div class="stat-label">中严重度</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number low">{summary.get('low_count', 0)}</div>
                    <div class="stat-label">低严重度</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(users)}</div>
                    <div class="stat-label">参与人数</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>问题清单</h2>
            <ul class="issue-list">
"""

        # 问题列表
        for issue in issues:
            severity = issue.get('severity', 'low')
            html += f"""
                <li class="issue-item {severity}">
                    <div class="issue-title">[{issue.get('dimension', '')}] {issue.get('title', '')}</div>
                    <div class="issue-meta">目标：{issue.get('goal_title', 'N/A')}</div>
                    <div class="issue-desc">{issue.get('description', '')}</div>
                </li>
"""

        html += f"""
            </ul>
        </div>
"""

        # 优化建议
        if suggestions:
            html += f"""
        <div class="card">
            <h2>优化建议</h2>
"""
            for s in suggestions:
                html += f"""
            <div class="suggestion-item">
                <div class="issue-title">{s.get('priority', '')}: {s.get('title', '')}</div>
                <div class="issue-meta">责任人：{s.get('owner', '待定')}</div>
                <div class="issue-desc">{s.get('description', '')}</div>
            </div>
"""
            html += """
        </div>
"""

        html += f"""
        <div class="footer">
            <p>绩效目标拆解诊断系统 v2.5 | 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""

        # 添加用户反馈入口
        html += FEEDBACK_SECTION_HTML
        return html

    def save_output(self, content):
        """保存输出"""
        output_path = self.args.output

        # 根据格式自动调整扩展名
        fmt = self.args.format
        if fmt == 'markdown' and not output_path.endswith('.md'):
            output_path = output_path.rsplit('.', 1)[0] + '.md'
        elif fmt == 'html' and not output_path.endswith('.html'):
            output_path = output_path.rsplit('.', 1)[0] + '.html'
        elif fmt == 'text' and not output_path.endswith('.txt'):
            output_path = output_path.rsplit('.', 1)[0] + '.txt'

        # 确保目录存在
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"\n💾 结果已保存到：{output_path}")
        return output_path

    def run(self):
        """运行完整流程"""
        print("=" * 60)
        print("🎯 绩效目标拆解诊断工具 v2.7")
        print("=" * 60)

        # 1. 解析参数
        self.parse_args()

        # 2. 校验输入
        self.validate_input()

        # 3. 采集数据
        self.collect_data()

        # 4. 校验数据
        data_valid = self.validate_data()
        if not data_valid:
            print("\n❌ 数据校验失败，请检查输入数据")
            sys.exit(1)

        # 如果只是校验，就到这里
        if self.args.validate:
            print("\n✅ 数据校验完成")
            return

        # 5. 运行诊断
        self.run_diagnosis()

        # 6. 格式化输出
        output_content = self.format_output()

        # 7. 保存输出
        self.save_output(output_content)

        print("\n" + "=" * 60)
        print("✅ 诊断完成！")
        print("=" * 60)


def main():
    tool = GoalDiagnosisTool()
    tool.run()


if __name__ == '__main__':
    main()
