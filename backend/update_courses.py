from sqlalchemy.orm import Session
from app.infra.database import engine
from app.models.school import AICourse
import json

def update_courses():
    with Session(engine) as db:
        courses = db.query(AICourse).all()
        for course in courses:
            target_skills = course.target_skills.split(", ") if course.target_skills else ["前沿技术"]
            
            outline = {
                "weeks": [
                    {
                        "week_number": 1,
                        "theme": f"{target_skills[0]} 核心概念与环境搭建",
                        "goal": "掌握核心底层原理、配置开发环境并完成首个 Demo",
                        "tasks": [
                            {"name": "开发环境准备", "description": "配置本地开发环境，安装必要的 SDK 与依赖库", "resource_links": []},
                            {"name": "核心理论学习", "description": "深入理解架构设计理念与核心工作流", "resource_links": []},
                            {"name": "Hello World 实战", "description": "基于官方文档，动手完成第一个基础演示程序", "resource_links": []}
                        ],
                        "passing_criteria": "成功运行 Demo 并通过随堂知识测验 (80分及格)"
                    },
                    {
                        "week_number": 2,
                        "theme": "进阶核心功能开发",
                        "goal": "能够独立使用高级特性完成复杂业务需求",
                        "tasks": [
                            {"name": "组件化与模块化设计", "description": "学习如何进行代码拆分与高内聚设计", "resource_links": []},
                            {"name": "状态管理与数据流", "description": "掌握复杂状态同步及数据传递的最佳实践", "resource_links": []},
                            {"name": "API 交互实战", "description": "与后端服务或第三方 API 进行数据交互与异常处理", "resource_links": []}
                        ],
                        "passing_criteria": "完成阶段性作业，实现一个具备完整数据流的模块"
                    },
                    {
                        "week_number": 3,
                        "theme": "性能优化与工程化",
                        "goal": "掌握线上部署标准、工程化规范及性能调优",
                        "tasks": [
                            {"name": "性能分析与调优", "description": "使用 Profiler 工具找出性能瓶颈并进行优化", "resource_links": []},
                            {"name": "自动化测试", "description": "编写单元测试与端到端测试，保证代码质量", "resource_links": []},
                            {"name": "CI/CD 基础", "description": "配置自动化构建与部署流水线", "resource_links": []}
                        ],
                        "passing_criteria": "测试覆盖率达到 70% 以上，并成功通过 CI 检查"
                    },
                    {
                        "week_number": 4,
                        "theme": "企业级项目实战与答辩",
                        "goal": "从零到一构建并上线一个完整的企业级项目",
                        "tasks": [
                            {"name": "需求分析与架构设计", "description": "完成毕业项目的技术选型与数据库设计", "resource_links": []},
                            {"name": "全栈开发实战", "description": "独立开发整个项目，并处理边缘情况与安全问题", "resource_links": []},
                            {"name": "上线部署与总结", "description": "将项目部署至云服务器，并准备结课答辩", "resource_links": []}
                        ],
                        "passing_criteria": "通过导师代码评审 (Code Review) 及最终答辩"
                    }
                ]
            }
            course.outline = json.dumps(outline)
        db.commit()
        print(f"Updated {len(courses)} courses.")

if __name__ == '__main__':
    update_courses()
