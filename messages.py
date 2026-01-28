"""
LINE 訊息模板建構模組
支援 Flex Message 和 Quick Reply
"""

from linebot.v3.messaging import (
    TextMessage,
    FlexMessage,
    FlexContainer,
    QuickReply,
    QuickReplyItem,
    MessageAction,
    FlexBubble,
    FlexBox,
    FlexText,
    FlexSeparator,
    FlexButton
)
import json


def create_quick_reply(items: list) -> QuickReply:
    """
    建立 Quick Reply
    items: [{'label': '顯示文字', 'text': '發送文字'}, ...]
    """
    quick_reply_items = []
    for item in items:
        quick_reply_items.append(
            QuickReplyItem(
                action=MessageAction(
                    label=item['label'],
                    text=item['text']
                )
            )
        )
    return QuickReply(items=quick_reply_items)


def create_menu_message() -> FlexMessage:
    """建立主選單 Flex Message"""
    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📋 成員名冊機器人",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#1DB446"
                }
            ],
            "paddingBottom": "md"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "請選擇功能：",
                    "size": "sm",
                    "color": "#666666",
                    "margin": "none"
                }
            ],
            "paddingTop": "none"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "📝 登記",
                                "text": "/登記"
                            },
                            "color": "#1DB446"
                        },
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "✏️ 修改",
                                "text": "/修改"
                            },
                            "color": "#1DB446"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "🔍 查詢",
                                "text": "/查詢"
                            },
                            "color": "#5B82DB"
                        },
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "📋 名冊 🔒",
                                "text": "/名冊"
                            },
                            "color": "#DB5B5B"
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "👤 我是誰",
                                "text": "/我是誰"
                            }
                        },
                        {
                            "type": "button",
                            "style": "secondary",
                            "height": "sm",
                            "action": {
                                "type": "message",
                                "label": "❓ 說明",
                                "text": "/說明"
                            }
                        }
                    ]
                }
            ],
            "flex": 0
        }
    }

    return FlexMessage(
        alt_text="成員名冊機器人選單",
        contents=FlexContainer.from_dict(bubble)
    )


def create_roster_text_message(members: list, total: int) -> TextMessage:
    """建立純文字版名冊（用於顯示全部成員，避免 Flex Message 大小限制）"""
    if not members:
        return TextMessage(text="📋 目前沒有任何登記資料")

    lines = [f"📋 成員名冊（全部 {total} 人）", ""]

    for i, member in enumerate(members, start=1):
        lines.append(f"{i}. {member['line_display_name']} ↔ {member['game_name']}")

    return TextMessage(text="\n".join(lines))


def create_roster_message(members: list, page: int, total_pages: int, total: int, show_all: bool = False) -> FlexMessage:
    """建立名冊 Flex Message"""

    # 建立成員列表
    member_contents = []

    if not members:
        member_contents.append({
            "type": "text",
            "text": "目前沒有任何登記資料",
            "size": "sm",
            "color": "#888888",
            "align": "center"
        })
    else:
        start_num = 1 if show_all else (page - 1) * 20 + 1
        for i, member in enumerate(members, start=start_num):
            member_contents.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{i}.",
                        "size": "sm",
                        "color": "#888888",
                        "flex": 0,
                        "margin": "none"
                    },
                    {
                        "type": "text",
                        "text": f"{member['line_display_name']}",
                        "size": "sm",
                        "color": "#333333",
                        "flex": 4,
                        "margin": "sm"
                    },
                    {
                        "type": "text",
                        "text": "↔",
                        "size": "sm",
                        "color": "#888888",
                        "flex": 0,
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": f"{member['game_name']}",
                        "size": "sm",
                        "color": "#1DB446",
                        "flex": 4,
                        "margin": "sm",
                        "align": "end"
                    }
                ],
                "margin": "sm"
            })

    # 建立頁面資訊
    if show_all:
        page_info = f"全部 {total} 人"
    else:
        page_info = f"第 {page}/{total_pages} 頁，共 {total} 人"

    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": "📋 成員名冊",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#1DB446",
                    "flex": 4
                },
                {
                    "type": "text",
                    "text": page_info,
                    "size": "xs",
                    "color": "#888888",
                    "align": "end",
                    "gravity": "center",
                    "flex": 3
                }
            ],
            "paddingBottom": "sm"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": member_contents,
            "paddingTop": "sm"
        }
    }

    # 如果有多頁且不是顯示全部，加入分頁按鈕
    if total_pages > 1 and not show_all:
        footer_buttons = []

        # 上一頁按鈕
        if page > 1:
            footer_buttons.append({
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": "⬅️ 上一頁",
                    "text": f"/名冊 {page - 1}"
                }
            })

        # 顯示全部按鈕
        footer_buttons.append({
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "message",
                "label": "📄 全部",
                "text": "/名冊 全部"
            },
            "color": "#5B82DB"
        })

        # 下一頁按鈕
        if page < total_pages:
            footer_buttons.append({
                "type": "button",
                "style": "secondary",
                "height": "sm",
                "action": {
                    "type": "message",
                    "label": "➡️ 下一頁",
                    "text": f"/名冊 {page + 1}"
                }
            })

        bubble["footer"] = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": footer_buttons
        }

    return FlexMessage(
        alt_text=f"成員名冊 - {page_info}",
        contents=FlexContainer.from_dict(bubble)
    )


def create_search_result_message(query: str, results: list) -> FlexMessage:
    """建立查詢結果 Flex Message"""

    if not results:
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🔍 查詢「{query}」",
                        "weight": "bold",
                        "size": "md",
                        "color": "#5B82DB"
                    },
                    {
                        "type": "text",
                        "text": "查無相關結果",
                        "size": "sm",
                        "color": "#888888",
                        "margin": "md"
                    }
                ]
            }
        }
    else:
        member_contents = []
        for member in results:
            member_contents.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": f"• {member['line_display_name']}",
                        "size": "sm",
                        "color": "#333333",
                        "flex": 4
                    },
                    {
                        "type": "text",
                        "text": "↔",
                        "size": "sm",
                        "color": "#888888",
                        "flex": 0
                    },
                    {
                        "type": "text",
                        "text": f"{member['game_name']}",
                        "size": "sm",
                        "color": "#1DB446",
                        "flex": 4,
                        "align": "end"
                    }
                ],
                "margin": "sm"
            })

        bubble = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🔍 查詢「{query}」",
                        "weight": "bold",
                        "size": "md",
                        "color": "#5B82DB"
                    },
                    {
                        "type": "text",
                        "text": f"找到 {len(results)} 筆結果",
                        "size": "xs",
                        "color": "#888888",
                        "margin": "sm"
                    }
                ],
                "paddingBottom": "sm"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": member_contents,
                "paddingTop": "none"
            }
        }

    return FlexMessage(
        alt_text=f"查詢「{query}」的結果",
        contents=FlexContainer.from_dict(bubble)
    )


def create_profile_message(member: dict, line_display_name: str, is_registered: bool) -> FlexMessage:
    """建立個人資料 Flex Message"""

    if not is_registered:
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "👤 我的資料",
                        "weight": "bold",
                        "size": "md",
                        "color": "#5B82DB"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"LINE 名稱：{line_display_name}",
                                "size": "sm",
                                "color": "#333333"
                            },
                            {
                                "type": "text",
                                "text": "尚未登記",
                                "size": "sm",
                                "color": "#888888",
                                "margin": "sm"
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "action": {
                            "type": "message",
                            "label": "📝 立即登記",
                            "text": "/登記"
                        },
                        "color": "#1DB446",
                        "height": "sm"
                    }
                ]
            }
        }
    else:
        admin_badge = " 👑" if member['is_admin'] else ""
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"👤 我的資料{admin_badge}",
                        "weight": "bold",
                        "size": "md",
                        "color": "#5B82DB"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "LINE 名稱",
                                        "size": "sm",
                                        "color": "#888888",
                                        "flex": 2
                                    },
                                    {
                                        "type": "text",
                                        "text": member['line_display_name'],
                                        "size": "sm",
                                        "color": "#333333",
                                        "flex": 4,
                                        "align": "end"
                                    }
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "遊戲名稱",
                                        "size": "sm",
                                        "color": "#888888",
                                        "flex": 2
                                    },
                                    {
                                        "type": "text",
                                        "text": member['game_name'],
                                        "size": "sm",
                                        "color": "#1DB446",
                                        "weight": "bold",
                                        "flex": 4,
                                        "align": "end"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "message",
                            "label": "✏️ 修改名稱",
                            "text": "/修改"
                        },
                        "height": "sm"
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "action": {
                            "type": "message",
                            "label": "📋 查看名冊",
                            "text": "/名冊"
                        },
                        "height": "sm"
                    }
                ]
            }
        }

    return FlexMessage(
        alt_text="我的資料",
        contents=FlexContainer.from_dict(bubble)
    )


def create_help_message() -> FlexMessage:
    """建立說明 Flex Message"""

    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📋 指令說明",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#1DB446"
                }
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "【一般指令】",
                    "weight": "bold",
                    "size": "sm",
                    "color": "#5B82DB"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "xs",
                    "contents": [
                        {"type": "text", "text": "/登記 [遊戲名稱]", "size": "sm", "color": "#333333"},
                        {"type": "text", "text": "  綁定 LINE 與遊戲角色", "size": "xs", "color": "#888888"},
                        {"type": "text", "text": "/修改 [新遊戲名稱]", "size": "sm", "color": "#333333", "margin": "sm"},
                        {"type": "text", "text": "  修改遊戲名稱", "size": "xs", "color": "#888888"},
                        {"type": "text", "text": "/查詢 [名稱]", "size": "sm", "color": "#333333", "margin": "sm"},
                        {"type": "text", "text": "  搜尋成員", "size": "xs", "color": "#888888"},
                        {"type": "text", "text": "/我是誰", "size": "sm", "color": "#333333", "margin": "sm"},
                        {"type": "text", "text": "  查看自己的資料", "size": "xs", "color": "#888888"}
                    ]
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "text",
                    "text": "【幹部指令】",
                    "weight": "bold",
                    "size": "sm",
                    "color": "#DB5B5B",
                    "margin": "lg"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "xs",
                    "contents": [
                        {"type": "text", "text": "/名冊", "size": "sm", "color": "#333333"},
                        {"type": "text", "text": "  顯示所有成員", "size": "xs", "color": "#888888"},
                        {"type": "text", "text": "/代登記 [LINE名] [遊戲名]", "size": "sm", "color": "#333333", "margin": "sm"},
                        {"type": "text", "text": "  幫其他成員登記", "size": "xs", "color": "#888888"},
                        {"type": "text", "text": "/刪除 [名稱]", "size": "sm", "color": "#333333", "margin": "sm"},
                        {"type": "text", "text": "  刪除成員資料", "size": "xs", "color": "#888888"},
                        {"type": "text", "text": "/設定管理員 [名稱]", "size": "sm", "color": "#333333", "margin": "sm"},
                        {"type": "text", "text": "  新增幹部", "size": "xs", "color": "#888888"}
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": "📋 名冊",
                        "text": "/名冊"
                    },
                    "color": "#1DB446"
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": "👤 我是誰",
                        "text": "/我是誰"
                    }
                }
            ]
        }
    }

    return FlexMessage(
        alt_text="指令說明",
        contents=FlexContainer.from_dict(bubble)
    )


def create_success_message(title: str, content: str, quick_actions: list = None) -> TextMessage:
    """建立成功訊息（含 Quick Reply）"""
    text = f"✅ {title}\n\n{content}"

    if quick_actions:
        return TextMessage(
            text=text,
            quick_reply=create_quick_reply(quick_actions)
        )
    return TextMessage(text=text)


def create_error_message(content: str, quick_actions: list = None) -> TextMessage:
    """建立錯誤訊息（含 Quick Reply）"""
    text = f"❌ {content}"

    if quick_actions:
        return TextMessage(
            text=text,
            quick_reply=create_quick_reply(quick_actions)
        )
    return TextMessage(text=text)


def create_input_prompt_message(command: str, prompt: str, examples: list = None) -> FlexMessage:
    """建立輸入提示 Flex Message（當指令缺少參數時）"""

    contents = [
        {
            "type": "text",
            "text": f"📝 {command}",
            "weight": "bold",
            "size": "md",
            "color": "#5B82DB"
        },
        {
            "type": "text",
            "text": prompt,
            "size": "sm",
            "color": "#333333",
            "margin": "md",
            "wrap": True
        }
    ]

    if examples:
        contents.append({
            "type": "text",
            "text": "範例：",
            "size": "xs",
            "color": "#888888",
            "margin": "lg"
        })
        for example in examples:
            contents.append({
                "type": "text",
                "text": f"  {example}",
                "size": "xs",
                "color": "#888888"
            })

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": contents
        }
    }

    return FlexMessage(
        alt_text=prompt,
        contents=FlexContainer.from_dict(bubble)
    )
