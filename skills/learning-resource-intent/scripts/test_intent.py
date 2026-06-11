#!/usr/bin/env python3
"""
学习资源需求分析测试脚本

基于 test-cases.md 中的 12 个测试样例验证 intent 分析的正确性。
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


# 添加当前脚本目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_intent import LearningResourceIntentAnalyzer


# 测试用例
TEST_CASES = [
    {
        'name': '样例1：宽泛数学资料',
        'query': '帮我找点数学学习资料',
        'expect_status': 'needs_clarification',
        'expect_domain': '数学',
        'expect_missing': ['learner_age_or_grade', 'core_topic'],
        'expect_questions_count': 2,
    },
    {
        'name': '样例2：明确主题但缺年龄',
        'query': '我要四则整数运算的学习资料',
        'expect_status': 'needs_clarification',
        'expect_topic': '四则整数运算',
        'expect_domain': '数学',
        'expect_missing': ['learner_age_or_grade'],
    },
    {
        'name': '样例3：主题、年龄、形式明确',
        'query': '给8岁孩子找四则混合运算练习题，最好能打印',
        'expect_status': 'ready',
        'expect_age': 8,
        'expect_topic': '四则混合运算',
        'expect_resource_goal': '练习',
        'expect_tasks_count': 1,
    },
    {
        'name': '样例4：儿童百科过宽',
        'query': '找点儿童百科',
        'expect_status': 'needs_clarification',
        'expect_domain': '百科',
        'expect_topic': '儿童百科',
        'expect_missing': ['learner_age_or_grade'],
    },
    {
        'name': '样例5：百科主题明确',
        'query': '找适合7岁孩子看的恐龙百科视频',
        'expect_status': 'ready',
        'expect_age': 7,
        'expect_topic': '恐龙百科',
        'expect_resource_types': ['视频'],
    },
    {
        'name': '样例6：唐诗宋词启蒙音频',
        'query': '给5岁孩子找唐诗宋词启蒙音频',
        'expect_status': 'ready',
        'expect_age': 5,
        'expect_domain': '文学',
        'expect_topic': '唐诗宋词启蒙',
        'expect_resource_goal': '听赏',
    },
    {
        'name': '样例7：儿歌资源',
        'query': '给4岁孩子找几首英文儿歌',
        'expect_status': 'ready',
        'expect_age': 4,
        'expect_domain': '音乐',
        'expect_topic': '英文儿歌',
    },
    {
        'name': '样例8：幼小衔接场景',
        'query': '孩子快上一年级了，想做幼小衔接',
        'expect_status': 'needs_clarification',
        'expect_profile': '幼小衔接',
        'expect_stage': '学前',
    },
    {
        'name': '样例9：儿童百科视频和图文',
        'query': '帮孩子找恐龙百科视频和图文资料',
        'expect_status': 'needs_clarification',
        'expect_domain': '百科',
        'expect_topic': '恐龙百科',
        'expect_missing': ['learner_age_or_grade'],
    },
    {
        'name': '样例10：可打印练习题，多来源候选',
        'query': '给8岁孩子找可打印四则混合运算练习题',
        'expect_status': 'ready',
        'expect_age': 8,
        'expect_topic': '四则混合运算',
        'expect_tasks_min': 1,
    },
    {
        'name': '样例11：本地资料库优先',
        'query': '看看本地有没有适合6岁孩子的识字资料',
        'expect_status': 'ready',
        'expect_age': 6,
        'expect_intent_type': 'local_lookup',
        'expect_tasks_count': 2,
    },
    {
        'name': '样例12：家长要求过宽且下载',
        'query': '帮我把适合6岁孩子的学习资料都下载下来',
        'expect_status': 'needs_clarification',
        'expect_age': 6,
        'expect_missing': ['core_topic'],
        'expect_request_scope': 'full_coverage',
        'expect_coverage_targets': ['resource_set'],
    },
    {
        'name': '样例13：全套课程资料是通用范围意图',
        'query': '我要三年级数学课程的全部资料',
        'expect_status': 'ready',
        'expect_grade': 3,
        'expect_domain': '数学',
        'expect_request_scope': 'full_coverage',
        'expect_coverage_targets': ['resource_set', 'video'],
        'expect_tasks_min': 1,
    },
    {
        'name': '样例14：版本只是检索约束',
        'query': '我要三年级语文统编版资料',
        'expect_status': 'needs_clarification',
        'expect_grade': 3,
        'expect_domain': '语文',
        'expect_intent_not_type': 'exact_resource',
        'expect_missing': ['core_topic'],
        'expect_request_scope': 'candidate_set',
    },
]


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.analyzer = LearningResourceIntentAnalyzer()
        self.passed = 0
        self.failed = 0
        self.results = []

    def run_test(self, case: Dict[str, Any]) -> bool:
        """运行单个测试用例"""
        name = case['name']
        query = case['query']

        print(f'\n测试: {name}')
        print(f'查询: "{query}"')

        # 执行分析
        result = self.analyzer.analyze(query)

        # 验证结果
        success = True
        failures = []

        # 检查状态
        if 'expect_status' in case:
            expect_status = case['expect_status']
            actual_status = result['status']
            if expect_status != actual_status:
                success = False
                failures.append(f'状态不匹配: 期望 {expect_status}, 实际 {actual_status}')

        # 检查年龄
        if 'expect_age' in case:
            expect_age = case['expect_age']
            actual_age = result['learner_age']
            if expect_age != actual_age:
                success = False
                failures.append(f'年龄不匹配: 期望 {expect_age}, 实际 {actual_age}')

        # 检查年级
        if 'expect_grade' in case:
            expect_grade = case['expect_grade']
            actual_grade = result['grade']
            if expect_grade != actual_grade:
                success = False
                failures.append(f'年级不匹配: 期望 {expect_grade}, 实际 {actual_grade}')

        # 检查主题
        if 'expect_topic' in case:
            expect_topic = case['expect_topic']
            actual_topic = result['core_topic']
            if expect_topic != actual_topic:
                success = False
                failures.append(f'主题不匹配: 期望 {expect_topic}, 实际 {actual_topic}')

        # 检查学习领域
        if 'expect_domain' in case:
            expect_domain = case['expect_domain']
            actual_domain = result['learning_domain']
            if expect_domain != actual_domain:
                success = False
                failures.append(f'学习领域不匹配: 期望 {expect_domain}, 实际 {actual_domain}')

        # 检查资源目标
        if 'expect_resource_goal' in case:
            expect_goal = case['expect_resource_goal']
            actual_goal = result['resource_goal']
            if expect_goal != actual_goal:
                success = False
                failures.append(f'资源目标不匹配: 期望 {expect_goal}, 实际 {actual_goal}')

        # 检查资源类型
        if 'expect_resource_types' in case:
            expect_types = set(case['expect_resource_types'])
            actual_types = set(result['resource_types'])
            if not expect_types.issubset(actual_types):
                success = False
                failures.append(f'资源类型不匹配: 期望包含 {expect_types}, 实际 {actual_types}')

        # 检查缺失槽位
        if 'expect_missing' in case:
            expect_missing = set(case['expect_missing'])
            actual_missing = set(result['missing_slots'])
            # 只检查期望的缺失槽位是否都在实际缺失中
            if not expect_missing.issubset(actual_missing):
                success = False
                failures.append(f'缺失槽位不匹配: 期望包含 {expect_missing}, 实际 {actual_missing}')

        # 检查澄清问题数量
        if 'expect_questions_count' in case:
            expect_count = case['expect_questions_count']
            actual_count = len(result['clarifying_questions'])
            if expect_count != actual_count:
                success = False
                failures.append(f'澄清问题数量不匹配: 期望 {expect_count}, 实际 {actual_count}')

        # 检查任务数量
        if 'expect_tasks_count' in case:
            expect_count = case['expect_tasks_count']
            actual_count = len(result['execution_tasks'])
            if expect_count != actual_count:
                success = False
                failures.append(f'任务数量不匹配: 期望 {expect_count}, 实际 {actual_count}')

        # 检查任务数量范围
        if 'expect_tasks_min' in case:
            expect_min = case['expect_tasks_min']
            actual_count = len(result['execution_tasks'])
            if actual_count < expect_min:
                success = False
                failures.append(f'任务数量不足: 期望至少 {expect_min}, 实际 {actual_count}')

        # 检查意图类型
        if 'expect_intent_type' in case:
            expect_type = case['expect_intent_type']
            actual_type = result['intent_type']
            if expect_type != actual_type:
                success = False
                failures.append(f'意图类型不匹配: 期望 {expect_type}, 实际 {actual_type}')

        # 检查不应出现的意图类型
        if 'expect_intent_not_type' in case:
            expect_not_type = case['expect_intent_not_type']
            actual_type = result['intent_type']
            if expect_not_type == actual_type:
                success = False
                failures.append(f'意图类型不应为 {expect_not_type}')

        # 检查请求范围
        if 'expect_request_scope' in case:
            expect_scope = case['expect_request_scope']
            actual_scope = result.get('request_scope')
            if expect_scope != actual_scope:
                success = False
                failures.append(f'请求范围不匹配: 期望 {expect_scope}, 实际 {actual_scope}')

        # 检查覆盖面向
        if 'expect_coverage_targets' in case:
            expect_targets = set(case['expect_coverage_targets'])
            actual_targets = set(result.get('coverage_targets') or [])
            if not expect_targets.issubset(actual_targets):
                success = False
                failures.append(f'覆盖面向不匹配: 期望包含 {expect_targets}, 实际 {actual_targets}')

        # 检查学习者画像
        if 'expect_profile' in case:
            expect_profile = case['expect_profile']
            actual_profile = result['learner_profile']
            if expect_profile != actual_profile:
                success = False
                failures.append(f'学习者画像不匹配: 期望 {expect_profile}, 实际 {actual_profile}')

        # 检查阶段
        if 'expect_stage' in case:
            expect_stage = case['expect_stage']
            actual_stage = result['stage']
            if expect_stage != actual_stage:
                success = False
                failures.append(f'学习阶段不匹配: 期望 {expect_stage}, 实际 {actual_stage}')

        # 输出结果
        if success:
            print('  [PASS] 通过')
            self.passed += 1
        else:
            print('  [FAIL] 失败')
            for failure in failures:
                print(f'    - {failure}')
            self.failed += 1

        self.results.append({
            'name': name,
            'success': success,
            'failures': failures,
        })

        return success

    def run_all(self) -> bool:
        """运行所有测试用例"""
        print('=' * 60)
        print('学习资源需求分析测试')
        print('=' * 60)

        for case in TEST_CASES:
            self.run_test(case)

        # 输出总结
        print('\n' + '=' * 60)
        print('测试总结')
        print('=' * 60)
        print(f'总数: {len(TEST_CASES)}')
        print(f'通过: {self.passed}')
        print(f'失败: {self.failed}')
        print(f'通过率: {self.passed / len(TEST_CASES) * 100:.1f}%')

        if self.failed > 0:
            print('\n失败的测试:')
            for result in self.results:
                if not result['success']:
                    print(f'  - {result["name"]}')
                    for failure in result['failures']:
                        print(f'    * {failure}')

        return self.failed == 0


def main():
    runner = TestRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
