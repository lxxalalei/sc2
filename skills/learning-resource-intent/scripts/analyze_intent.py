#!/usr/bin/env python3
"""
学习资源需求分析脚本

分析用户自然语言学习资源需求，输出结构化意图、澄清问题和执行任务。

用法:
    python3 analyze_intent.py "给8岁孩子找数学练习题"
    python3 analyze_intent.py --input-json input.json
    python3 analyze_intent.py --input-json input.json --output-json output.json
"""

import argparse
import json
import re
import sys
from typing import Any, Optional


class LearningResourceIntentAnalyzer:
    """学习资源需求分析器"""

    # 年龄相关模式
    AGE_PATTERNS = [
        r'(\d+)\s*岁',
        r'(\d+)\s*周岁',
        r'(\d+)岁',
        r'年级?为\s*(\d+)',
    ]

    # 年级映射
    GRADE_MAPPING = {
        '一年级': 1, '二年级': 2, '三年级': 3, '四年级': 4,
        '五年级': 5, '六年级': 6, '七年级': 7, '八年级': 8,
        '九年级': 9, '初一': 7, '初二': 8, '初三': 9,
    }

    # 阶段映射（年龄->阶段）
    AGE_TO_STAGE = {
        (3, 5): '学前',
        (6, 7): '小学低年级',
        (8, 9): '小学低年级',
        (10, 11): '小学中年级',
        (12, 12): '小学高年级',
    }

    # 学科关键词映射
    DOMAIN_KEYWORDS = {
        '数学': ['数学', '算术', '计算', '四则', '加减乘除', '几何', '代数'],
        '语文': ['语文', '拼音', '汉字', '识字', '阅读', '写作', '作文'],
        '英语': ['英语', '英文', 'abc', 'phonics', '自然拼读'],
        '科学': ['科学', '物理', '化学', '生物', '实验'],
        '百科': ['百科', '知识'],
        '文学': ['文学', '唐诗', '宋词', '古诗', '诗歌', '成语', '故事'],
        '音乐': ['音乐', '歌曲', '旋律'],
        '艺术': ['美术', '画画', '绘画', '手工', '折纸', '剪纸'],
        '体育': ['体育', '运动', '游戏', '跳绳', '跑步'],
    }

    # 主题映射
    TOPIC_KEYWORDS = {
        '四则整数运算': ['四则', '加减乘除', '整数运算'],
        '四则混合运算': ['混合运算', '四则混合运算'],
        '拼音识字': ['拼音', '识字', '汉字'],
        '唐诗宋词启蒙': ['唐诗', '宋词', '古诗', '诗词'],
        '唐诗宋词': ['唐诗', '宋词', '古诗', '诗词'],
        '儿童百科': ['儿童百科', '百科'],
        '恐龙百科': ['恐龙', '恐龙百科'],
        '儿歌': ['儿歌', '童谣'],
        '英文儿歌': ['英文儿歌', '英语儿歌'],
        '绘本': ['绘本', '图画书'],
        '英语启蒙': ['英语启蒙', '英文启蒙'],
    }

    # 资源类型关键词
    RESOURCE_TYPE_KEYWORDS = {
        '教材': ['教材', '课本', '教科书', '电子教材'],
        '课件': ['课件', 'ppt', '演示文稿', '教案'],
        '习题': ['习题', '练习', '练一练', '题', '作业', '巩固'],
        '试卷': ['试卷', '测试', '考试'],
        '视频': ['视频', '网课', '讲解', '课程'],
        '音频': ['音频', '录音', '听', 'mp3'],
        '图片': ['图片', '图像', '插图'],
        '绘本': ['绘本', '图画书'],
        '游戏': ['游戏', '互动'],
        '百科文章': ['百科', '图文', '文章'],
    }

    # 学习目标关键词
    GOAL_KEYWORDS = {
        '启蒙': ['启蒙', '入门', '基础', '零基础'],
        '预习': ['预习', '提前学'],
        '复习': ['复习', '巩固'],
        '练习': ['练习', '习题', '做题'],
        '拓展': ['拓展', '延伸', '扩展'],
        '阅读': ['阅读', '看书', '读书'],
        '听赏': ['听', '听赏', '聆听'],
        '备课': ['备课', '老师用', '上课用', '课堂教学'],
        '查阅': ['查阅', '参考', '资料'],
    }

    # 格式偏好关键词
    FORMAT_KEYWORDS = {
        'pdf': ['pdf', '可打印', '打印'],
        'doc': ['doc', 'word', '文档', '可打印', '打印'],
        'ppt': ['ppt', '演示文稿'],
        '视频': ['视频'],
        '音频': ['音频', 'mp3'],
    }

    # 来源偏好
    SOURCE_KEYWORDS = {
        '本地资料库': ['本地', '本地资料库', '已有'],
        '官方': ['官方', '国家平台', '智慧教育'],
        '出版社': ['出版社'],
    }

    # 难度关键词
    DIFFICULTY_KEYWORDS = {
        '启蒙': ['启蒙', '入门', '简单'],
        '基础': ['基础', '初级'],
        '同步': ['同步', '教材同步'],
        '提高': ['提高', '进阶'],
        '竞赛': ['竞赛', '奥数'],
    }

    def __init__(self):
        """初始化分析器"""
        self.query = ""
        self.normalized_query = ""
        self.slots = {}
        self.status = "ready"
        self.intent_type = "topic_resource"
        self.confidence = 0.0
        self.missing_slots = []
        self.clarifying_questions = []
        self.execution_tasks = []
        self.ranking_profile = {}

    def analyze(self, user_query: str, context: Optional[dict] = None) -> dict:
        """
        分析用户查询

        Args:
            user_query: 用户自然语言查询
            context: 上下文信息（可选）

        Returns:
            结构化意图分析结果
        """
        self.query = user_query.strip()
        self.normalized_query = self._normalize_query(self.query)
        self.slots = {}
        self.status = "ready"
        self.intent_type = "topic_resource"
        self.confidence = 0.0
        self.missing_slots = []
        self.clarifying_questions = []
        self.execution_tasks = []
        self.ranking_profile = {}
        context = context or {}

        # 1. 槽位抽取
        self._extract_slots()

        # 2. 判断意图类型
        self._determine_intent_type()

        # 3. 判断是否需要澄清
        self._determine_clarification_needs()

        # 4. 生成执行任务
        if self.status == "ready":
            self._generate_execution_tasks()
            self._build_ranking_profile()

        # 5. 构建结果
        return self._build_result()

    def _normalize_query(self, query: str) -> str:
        """标准化查询文本"""
        # 去除多余空格
        query = re.sub(r'\s+', ' ', query)
        # 去除特殊字符（保留中文、英文、数字、常用标点）
        query = re.sub(r"[^一-龥a-zA-Z0-9，。、？！；：\"'（）《》\s]", '', query)
        return query.strip()

    def _extract_slots(self):
        """抽取所有槽位"""
        self.slots['learner_age'] = self._extract_age()
        self.slots['grade'] = self._extract_grade()
        self.slots['learner_profile'] = self._extract_learner_profile()
        self.slots['stage'] = self._infer_stage()
        self.slots['learning_domain'] = self._extract_learning_domain()
        self.slots['subject'] = self._extract_subject()
        self.slots['core_topic'] = self._extract_core_topic()
        self.slots['subtopics'] = self._extract_subtopics()
        self.slots['resource_types'] = self._extract_resource_types()
        self.slots['resource_goal'] = self._extract_resource_goal()
        self.slots['difficulty'] = self._extract_difficulty()
        self.slots['format_preferences'] = self._extract_format_preferences()
        self.slots['source_preferences'] = self._extract_source_preferences()
        self.slots['version'] = self._extract_version()
        self.slots['volume'] = self._extract_volume()
        self.slots['request_scope'] = self._extract_request_scope()
        self.slots['coverage_targets'] = self._extract_coverage_targets()
        self.slots['constraints'] = self._extract_constraints()

    def _extract_age(self) -> Optional[int]:
        """抽取年龄"""
        for pattern in self.AGE_PATTERNS:
            match = re.search(pattern, self.query)
            if match:
                age = int(match.group(1))
                if 3 <= age <= 12:
                    return age
        return None

    def _infer_stage(self) -> Optional[str]:
        """推断学习阶段"""
        age = self.slots.get('learner_age')
        if age:
            for (min_age, max_age), stage in self.AGE_TO_STAGE.items():
                if min_age <= age <= max_age:
                    return stage

        # 从查询中直接提取阶段
        stage_keywords = {
            '学前': ['学前', '幼儿园'],
            '小学': ['小学'],
            '小学低年级': ['小学低年级', '一二年级'],
            '小学中年级': ['小学中年级', '三四年级'],
            '小学高年级': ['小学高年级', '五六年级'],
        }
        if self.slots.get('learner_profile') == '幼小衔接':
            return '学前'
        for stage, keywords in stage_keywords.items():
            if any(kw in self.query for kw in keywords):
                return stage
        return None

    def _extract_grade(self) -> Optional[int]:
        """抽取年级"""
        for grade_name, grade_num in self.GRADE_MAPPING.items():
            if grade_name in self.query:
                return grade_num
        return None

    def _extract_learner_profile(self) -> Optional[str]:
        """抽取学习者画像"""
        profiles = {
            '零基础': ['零基础', '入门'],
            '基础薄弱': ['基础薄弱', '基础差'],
            '进阶': ['进阶', '提高'],
            '兴趣启蒙': ['兴趣', '启蒙'],
            '备考': ['备考', '考试'],
            '幼小衔接': ['幼小衔接', '上一年级'],
            '亲子共读': ['亲子', '共读', '一起读'],
        }
        for profile, keywords in profiles.items():
            if any(kw in self.query for kw in keywords):
                return profile
        return None

    def _extract_learning_domain(self) -> Optional[str]:
        """抽取学习领域"""
        if any(kw in self.query for kw in ['儿歌', '童谣']):
            return '音乐'
        if any(kw in self.query for kw in ['恐龙', '宇宙', '太空', '人体', '动物', '植物']):
            return '百科'
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(kw in self.query for kw in keywords):
                return domain
        return None

    def _extract_subject(self) -> Optional[str]:
        """抽取学科（与学习领域类似，但更贴近学校学科）"""
        subjects = ['数学', '语文', '英语', '科学']
        for subject in subjects:
            if subject in self.query:
                return subject
        return self.slots.get('learning_domain')

    def _extract_core_topic(self) -> Optional[str]:
        """抽取核心主题"""
        # 先检查已知主题，按本次查询实际命中的关键词长度选择更具体的主题。
        matches: list[tuple[int, int, str]] = []
        for order, (topic, keywords) in enumerate(self.TOPIC_KEYWORDS.items()):
            matched_lengths = [len(keyword) for keyword in keywords if keyword in self.query]
            if matched_lengths:
                matches.append((max(matched_lengths), -order, topic))
        if matches:
            return sorted(matches, reverse=True)[0][2]

        # 如果没有匹配到已知主题，尝试从领域推断
        domain = self.slots.get('learning_domain')
        if domain == '数学':
            if any(kw in self.query for kw in ['计算', '运算']):
                return '计算练习'
            return '数学学习'
        elif domain == '语文':
            if '拼音' in self.query:
                return '拼音学习'
            elif '识字' in self.query:
                return '识字学习'
            return '语文学习'
        elif domain == '百科':
            # 尝试提取具体的百科主题
            encyclopedia_topics = ['恐龙', '宇宙', '太空', '地球', '人体', '动物', '植物']
            for topic in encyclopedia_topics:
                if topic in self.query:
                    return f'{topic}百科'
            return '儿童百科'

        return None

    def _extract_subtopics(self) -> list:
        """抽取子主题"""
        subtopics = []
        # 简单实现：提取查询中的名词作为潜在子主题
        # 这里可以扩展更复杂的逻辑
        if '恐龙' in self.query and '百科' in self.query:
            subtopics.append('恐龙')
        if '加减乘除' in self.query:
            subtopics.extend(['加法', '减法', '乘法', '除法'])
        return subtopics

    def _extract_resource_goal(self) -> str:
        """抽取学习目标"""
        resource_types = self.slots.get('resource_types') or self._extract_resource_types()
        if '音频' in resource_types:
            return '听赏'
        if '习题' in resource_types or '试卷' in resource_types:
            return '练习'
        if '视频' in resource_types:
            return '学习'

        for goal, keywords in self.GOAL_KEYWORDS.items():
            if any(kw in self.query for kw in keywords):
                return goal

        # 根据资源类型推断
        return '未指定'

    def _extract_resource_types(self) -> list:
        """抽取资源类型"""
        types = []
        if '儿歌' in self.query or '童谣' in self.query:
            types.extend(['音频', '视频', '歌词'])
        if '图文' in self.query:
            types.extend(['百科文章', '图片'])
        for rtype, keywords in self.RESOURCE_TYPE_KEYWORDS.items():
            if any(kw in self.query for kw in keywords):
                types.append(rtype)

        # 如果没有明确类型，根据关键词推断
        if not types:
            if '听' in self.query:
                types.append('音频')
            if '看' in self.query or '读' in self.query:
                types.append('视频')
                types.append('百科文章')
            if '练' in self.query or '题' in self.query:
                types.append('习题')

        return list(dict.fromkeys(types)) if types else []

    def _extract_difficulty(self) -> Optional[str]:
        """抽取难度"""
        for difficulty, keywords in self.DIFFICULTY_KEYWORDS.items():
            if any(kw in self.query for kw in keywords):
                return difficulty

        # 根据年龄推断
        age = self.slots.get('learner_age')
        if age and age <= 6:
            return '启蒙'

        return None

    def _extract_format_preferences(self) -> list:
        """抽取格式偏好"""
        formats = []
        for fmt, keywords in self.FORMAT_KEYWORDS.items():
            if any(kw in self.query for kw in keywords):
                formats.append(fmt.upper() if fmt in ['pdf', 'doc', 'ppt'] else fmt)
        return formats

    def _extract_source_preferences(self) -> list:
        """抽取来源偏好"""
        sources = []
        for source, keywords in self.SOURCE_KEYWORDS.items():
            if any(kw in self.query for kw in keywords):
                sources.append(source)
        return sources

    def _extract_version(self) -> Optional[str]:
        """抽取版本"""
        versions = ['人教版', '统编版', '北师大版', '苏教版', '外研版', '部编版']
        for version in versions:
            if version in self.query:
                return version
        return None

    def _extract_volume(self) -> Optional[str]:
        """抽取册次"""
        volumes = ['上册', '下册', '全一册', '必修', '选修']
        for volume in volumes:
            if volume in self.query:
                return volume
        return None

    def _extract_constraints(self) -> list:
        """抽取约束条件"""
        constraints = []
        if '可打印' in self.query or '打印' in self.query:
            constraints.append('适合打印')
        if '免费' in self.query:
            constraints.append('免费')
        if '中文' in self.query:
            constraints.append('中文')
        if '英文' in self.query:
            constraints.append('英文')
        return constraints

    def _extract_request_scope(self) -> str:
        """抽取通用请求范围，不绑定任何具体资源站或教材结构。"""
        query = self.query
        if re.search(r'https?://', query):
            return 'exact'
        if any(kw in query for kw in ['全部', '全套', '整套', '所有', '都要', '都下载', '完整', '合集']):
            return 'full_coverage'
        if any(kw in query for kw in ['找点', '推荐', '看看', '有哪些', '给我找', '帮我找']):
            return 'candidate_set'
        return 'candidate_set'

    def _extract_coverage_targets(self) -> list:
        """抽取全覆盖请求希望覆盖的资源面向。"""
        targets = []
        if any(kw in self.query for kw in ['资料', '资源', '材料']):
            targets.append('resource_set')
        if any(kw in self.query for kw in ['视频', '课程', '网课']):
            targets.append('video')
        if any(kw in self.query for kw in ['课件', 'ppt', '演示文稿']):
            targets.append('courseware')
        if any(kw in self.query for kw in ['习题', '练习', '作业', '试卷']):
            targets.append('practice')
        if any(kw in self.query for kw in ['音频', '儿歌', '听']):
            targets.append('audio')
        if any(kw in self.query for kw in ['图片', '图文', '绘本']):
            targets.append('image_or_article')
        return list(dict.fromkeys(targets))

    def _determine_intent_type(self):
        """判断意图类型"""
        query = self.query

        # 检查是否是本地查询
        if '本地' in query or '已有' in query:
            self.intent_type = 'local_lookup'
            return

        # 检查是否是精确资源请求。版本/年级/学科只是检索约束，不足以把普通
        # 学习资料需求升级为精确资源；只有 URL、明确题名，或教材定位信息较完整时才算。
        if re.search(r'https?://', query):
            self.intent_type = 'exact_resource'
            return
        has_named_resource = any(kw in query for kw in ['这份', '这个链接', '这门课', '这个课程', '资源名', '标题为'])
        has_precise_textbook = (
            '教材' in self.slots.get('resource_types', [])
            and self.slots.get('version')
            and self.slots.get('grade')
            and self.slots.get('subject')
            and self.slots.get('volume')
        )
        if has_named_resource or has_precise_textbook:
            self.intent_type = 'exact_resource'
            return

        # 检查是否是宽泛探索
        if '看看' in query or '了解' in query or '推荐' in query:
            self.intent_type = 'broad_exploration'
            return

        # 默认是主题资源请求
        self.intent_type = 'topic_resource'

    def _determine_clarification_needs(self):
        """判断是否需要澄清"""
        self.missing_slots = []
        self.clarifying_questions = []

        # 核心槽位检查
        age = self.slots.get('learner_age')
        grade = self.slots.get('grade')
        topic = self.slots.get('core_topic')
        goal = self.slots.get('resource_goal')
        resource_types = self.slots.get('resource_types')
        domain = self.slots.get('learning_domain')
        request_scope = self.slots.get('request_scope')

        # 1. 年龄/年级检查
        if not age and not grade:
            self.missing_slots.append('learner_age_or_grade')
            self.clarifying_questions.append('孩子大概几岁或几年级？')

        # 2. 主题检查
        if not topic and not domain:
            self.missing_slots.append('core_topic')
            self.clarifying_questions.append('想围绕哪个学习主题？比如数学、语文、英语、百科等。')

        # 3. 主题过宽检查
        # 当已有年龄/年级 + 学科领域 + 资源类型时，即使主题偏宽也可以搜索，
        # 因为来源 skill 会按年级和学科进一步筛选。
        wide_topics = ['数学学习', '语文学习', '英语学习', '儿童百科']
        has_enough_scope = (
            (age or grade)
            and domain
            and resource_types
        )
        full_coverage_with_searchable_scope = (
            request_scope == 'full_coverage'
            and has_enough_scope
        )
        if topic in wide_topics and not has_enough_scope and not any([
            '四则' in self.query,
            '拼音' in self.query,
            '识字' in self.query,
            any(sub in self.query for sub in ['恐龙', '宇宙', '人体', '动物'])
        ]):
            if 'core_topic' not in self.missing_slots:
                self.missing_slots.append('core_topic')
            self.clarifying_questions.append('想学哪个具体的主题？')

        # 4. 资源类型/目标检查
        if not resource_types and goal == '未指定':
            if '下载' in self.query or '都下载' in self.query:
                self.missing_slots.append('resource_goal_or_type')
                self.clarifying_questions.append('需要文档、图片、音频还是视频？')

        # 5. "都下载"类模糊请求检查
        if self.slots.get('request_scope') == 'full_coverage' and '下载' in self.query:
            if not topic or topic in ['儿童百科', '数学学习', '语文学习']:
                self.missing_slots.extend(['core_topic', 'resource_types'])
                self.clarifying_questions = [
                    '想围绕哪个主题？比如识字、数学启蒙、英语、百科或儿歌。',
                    '需要文档、图片、音频还是视频？'
                ]
                # 只保留这两个关键问题
                if 'learner_age_or_grade' in self.missing_slots:
                    self.missing_slots.remove('learner_age_or_grade')
                self.clarifying_questions = [q for q in self.clarifying_questions
                                             if '几岁' not in q]

        # 判断状态
        if self.missing_slots:
            self.status = 'needs_clarification'
            # 限制澄清问题数量，最多3个
            self.clarifying_questions = self.clarifying_questions[:3]
        else:
            self.status = 'ready'
            self.confidence = 0.85

    def _generate_execution_tasks(self):
        """生成执行任务"""
        self.execution_tasks = []

        # 构建查询语句
        age = self.slots.get('learner_age')
        grade = self.slots.get('grade')
        topic = self.slots.get('core_topic') or self.slots.get('learning_domain')
        resource_types = self.slots.get('resource_types', [])
        formats = self.slots.get('format_preferences', [])
        constraints = self.slots.get('constraints', [])

        # 基础查询词
        query_parts = []
        if age:
            query_parts.append(f'{age}岁')
        if grade:
            query_parts.append(f'{grade}年级')
        if topic:
            query_parts.append(topic)
        if resource_types:
            query_parts.extend(resource_types[:2])  # 最多加两个类型

        base_query = ' '.join(query_parts)

        # 过滤器
        filters = {
            'learner_age': age,
            'grade': grade,
            'learning_domain': self.slots.get('learning_domain'),
            'subject': self.slots.get('subject'),
            'core_topic': topic,
            'resource_types': resource_types,
            'format_preferences': formats,
            'version': self.slots.get('version'),
            'volume': self.slots.get('volume'),
            'request_scope': self.slots.get('request_scope'),
            'coverage_targets': self.slots.get('coverage_targets', []),
        }
        # 清理 None 值
        filters = {k: v for k, v in filters.items() if v not in (None, [], "")}

        # 任务1：本地搜索（如果有本地偏好或用户明确提到本地）
        if '本地' in self.query or any('本地' in s for s in self.slots.get('source_preferences', [])):
            task = {
                'task_id': 'task_000',
                'task_type': 'local_search',
                'target_skill': 'local-library-search',
                'action': 'search',
                'priority': 1,
                'query': f'{base_query} 本地资料',
                'filters': filters.copy(),
                'expected_resource_types': resource_types,
                'expected_formats': formats,
                'download_policy': 'never',
                'ranking_hints': {},
            }
            self.execution_tasks.append(task)

        # 任务2：Web 搜索（主要来源）
        web_query = base_query
        if '可打印' in self.query or any('打印' in c for c in constraints):
            web_query += ' 可打印'
            filters['printable'] = True
        if formats and 'PDF' in formats:
            web_query += ' PDF'

        task = {
            'task_id': f'task_{len(self.execution_tasks) + 1:03d}',
            'task_type': 'source_search',
            'target_skill': 'web-learning-search',
            'action': 'search',
            'priority': len(self.execution_tasks) + 1,
            'query': web_query,
            'filters': filters,
            'expected_resource_types': resource_types,
            'expected_formats': formats,
            'download_policy': 'after_user_selection',
            'ranking_hints': {
                'age_fit_required': bool(age or grade),
            },
        }
        if constraints:
            task['ranking_hints']['printable_required'] = any('打印' in c for c in constraints)

        self.execution_tasks.append(task)


    def _build_ranking_profile(self):
        """构建评分配置"""
        goal = self.slots.get('resource_goal', '未指定')
        resource_types = self.slots.get('resource_types', [])
        formats = self.slots.get('format_preferences', [])
        constraints = self.slots.get('constraints', [])

        # 主要目标
        primary_goal_map = {
            '练习': '练习题',
            '听赏': '可听赏',
            '阅读': '可阅读',
            '备课': '备课资料',
            '启蒙': '启蒙材料',
        }
        primary_goal = primary_goal_map.get(goal, '主题匹配')

        # 必须匹配
        must_match = []
        if self.slots.get('learner_age'):
            must_match.append('learner_age')
        if self.slots.get('core_topic'):
            must_match.append('core_topic')

        # 偏好
        prefer = []
        if 'PDF' in formats or any('打印' in c for c in constraints):
            prefer.extend(['PDF', '可打印'])
        if '官方' in self.slots.get('source_preferences', []):
            prefer.append('官方')

        # 避免
        avoid = ['来源不明', '强制下载器', '成人化内容']

        # 权重
        weights = {
            'relevance': 0.30,
            'age_fit': 0.20,
            'authority': 0.15,
            'accessibility': 0.10,
            'format': 0.10,
            'safety': 0.15,
        }

        # 根据目标调整权重
        if goal == '练习':
            weights['relevance'] = 0.35
            weights['format'] = 0.15
        elif goal == '听赏':
            weights['format'] = 0.20
            weights['relevance'] = 0.25

        self.ranking_profile = {
            'primary_goal': primary_goal,
            'must_match': must_match,
            'prefer': prefer,
            'avoid': avoid,
            'weights': weights,
        }

    def _build_result(self) -> dict:
        """构建最终结果"""
        result = {
            'intent_schema': 'learning-resource-intent/v1',
            'status': self.status,
            'intent_type': self.intent_type,
            'confidence': self.confidence,
            'normalized_query': self.normalized_query,
            'learner_age': self.slots.get('learner_age'),
            'stage': self.slots.get('stage'),
            'grade': self.slots.get('grade'),
            'learner_profile': self.slots.get('learner_profile'),
            'learning_domain': self.slots.get('learning_domain'),
            'subject': self.slots.get('subject'),
            'core_topic': self.slots.get('core_topic'),
            'subtopics': self.slots.get('subtopics', []),
            'resource_goal': self.slots.get('resource_goal'),
            'resource_types': self.slots.get('resource_types', []),
            'difficulty': self.slots.get('difficulty'),
            'format_preferences': self.slots.get('format_preferences', []),
            'source_preferences': self.slots.get('source_preferences', []),
            'version': self.slots.get('version'),
            'volume': self.slots.get('volume'),
            'request_scope': self.slots.get('request_scope'),
            'coverage_targets': self.slots.get('coverage_targets', []),
            'constraints': self.slots.get('constraints', []),
            'missing_slots': self.missing_slots,
            'clarifying_questions': self.clarifying_questions,
            'execution_tasks': self.execution_tasks,
            'ranking_profile': self.ranking_profile,
        }
        return result


def main():
    parser = argparse.ArgumentParser(description='分析学习资源需求')
    parser.add_argument('query', nargs='?', help='用户查询')
    parser.add_argument('--input-json', help='输入 JSON 文件路径')
    parser.add_argument('--output-json', help='输出 JSON 文件路径')
    parser.add_argument('--pretty', action='store_true', help='格式化输出 JSON')

    args = parser.parse_args()

    # 获取查询
    user_query = args.query
    if args.input_json:
        with open(args.input_json, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
            user_query = input_data.get('query', input_data.get('user_query', ''))

    if not user_query:
        parser.print_help()
        sys.exit(1)

    # 分析
    analyzer = LearningResourceIntentAnalyzer()
    result = analyzer.analyze(user_query)

    # 输出
    if args.output_json:
        with open(args.output_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2 if args.pretty else None)
        print(f'结果已保存到: {args.output_json}')
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
