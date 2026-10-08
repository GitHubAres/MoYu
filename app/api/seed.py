# 墨语 MoYu - Copyright (c) 2026 墨语（MoYu）贡献者
# Licensed under the MIT License. See LICENSE.
"""演示数据：一键创建示例作品《太虚仙途》。"""
from fastapi import APIRouter

from ..db import get_db, word_count

router = APIRouter(prefix="/seed", tags=["seed"])

SAMPLE_CH1 = """夜风拂过千仞绝壁，山门前的护宗大阵光纹泛起层层寒霜。叶临渊单手扣住古朴剑柄，指节因用力而泛出青白之色。天穹之巅，翻涌的雷云如倒悬古海，森罗死寂，压得整座通天峰几欲窒息。

陆清雪立在百步之外的白玉回廊下，素手轻抬，寒玉笛紧握于掌心，眸中掠过一丝难掩的震动。她认得那一式剑招——自祖师羽化八百年来，天剑宗上下再无一人能以元婴肉身引动如此暴烈的九天罡风。

"叶临渊，你疯了。"她轻声低语，声音却被轰鸣的雷声瞬息吞没。

崖巅之人并未回头，黑袍在罡风中猎猎作响。他只是缓缓将龙渊剑完全拔出，天地间的万钧雷霆竟在这一刻诡异地停滞了一瞬，仿佛连那浩瀚天道，也因这一柄凡铁铸就的古剑而微微屏息。"""

SAMPLE_CH2 = """寒夜凄清，霜色在残破的石阶上凝结成薄冰。林惊玄屏息蹲伏在檐角残瓦之后，指尖触碰剑柄，刺骨的凉意从精钢剑格直透心脉。山下的更夫敲响了三更，木柝声在空旷山谷中幽幽散开。

他等了三年。三年来，宗门上下都当那个雨夜的血案已被时光掩埋，唯有他知道，剑阁旧印上的裂痕不会在记忆里愈合。

更楼铜钲方鸣，七道青色袍影踏破霜雪呼啸而至，雁翎阵势刹那合围，雪亮刀风割裂夜幕。林惊玄眸光无波无澜，右臂微振，剑穗在风中划出一道沉静的弧度，身形不退反进，如一抹青烟飘然荡入杀阵中央。"""


@router.post("/demo", status_code=201)
def seed_demo():
    db = get_db()
    exists = db.execute("SELECT id FROM works WHERE title='太虚仙途（示例）'").fetchone()
    if exists:
        return {"ok": False, "message": "示例作品已存在", "work_id": exists["id"]}

    cur = db.execute(
        "INSERT INTO works(title, intro, genre, status, cover_color) VALUES (?,?,?,?,?)",
        ("太虚仙途（示例）",
         "仙穹浩渺，星霜流变。一名持剑守夜者，在玄冥裂隙间探寻大道本源的苍茫长卷。",
         "东方仙侠", "连载中", "#1B2A38"))
    work_id = cur.lastrowid

    v1 = db.execute("INSERT INTO volumes(work_id, title, sort_order) VALUES (?,?,1)",
                    (work_id, "卷一：问道青云")).lastrowid
    v2 = db.execute("INSERT INTO volumes(work_id, title, sort_order) VALUES (?,?,2)",
                    (work_id, "卷二：逆天改命")).lastrowid

    c1 = db.execute("INSERT INTO chapters(volume_id, title, content, status, word_count, sort_order) VALUES (?,?,?,?,?,1)",
                    (v1, "第一章 剑斩云霄", SAMPLE_CH1, "done", word_count(SAMPLE_CH1))).lastrowid
    c2 = db.execute("INSERT INTO chapters(volume_id, title, content, status, word_count, sort_order) VALUES (?,?,?,?,?,1)",
                    (v2, "第四十二章 霜夜回响", SAMPLE_CH2, "draft", word_count(SAMPLE_CH2))).lastrowid
    db.execute("INSERT INTO chapter_versions(chapter_id, content, word_count, source, label) VALUES (?,?,?,'manual','初始手稿')",
               (c1, SAMPLE_CH1, word_count(SAMPLE_CH1)))

    # 大纲节点
    n1 = db.execute("INSERT INTO outline_nodes(work_id, parent_id, title, synopsis, status, chapter_id, sort_order) VALUES (?,?,?,?,?,?,1)",
                    (work_id, None, "卷一：问道青云", "凡尘问道，起承转合已闭环", "done", None)).lastrowid
    node1 = db.execute("INSERT INTO outline_nodes(work_id, parent_id, title, synopsis, status, chapter_id, sort_order) VALUES (?,?,?,?,?,?,1)",
               (work_id, n1, "第一章 剑斩云霄", "叶临渊护宗大阵前顿悟太虚剑经第七层，一剑斩落敌方先锋长老。", "done", c1)).lastrowid
    n2 = db.execute("INSERT INTO outline_nodes(work_id, parent_id, title, synopsis, status, chapter_id, sort_order) VALUES (?,?,?,?,?,?,2)",
                    (work_id, None, "卷二：逆天改命", "当篇推进中：宗门内乱暗涌", "active", None)).lastrowid
    node2 = db.execute("INSERT INTO outline_nodes(work_id, parent_id, title, synopsis, status, chapter_id, sort_order) VALUES (?,?,?,?,?,?,1)",
               (work_id, n2, "第四十二章 霜夜回响", "林惊玄雪夜复仇，雁翎阵中初露锋芒。", "active", c2)).lastrowid

    # 设定
    e1 = db.execute("""INSERT INTO entities(work_id, category, name, fields_json, content, tags)
                       VALUES (?,?,?,?,?,?)""",
                    (work_id, "character", "叶临渊",
                     '{"身份":"天剑宗执剑长老","性格":"沉稳内敛，外冷内热","背景":"幼时满门被灭，为祖师所救","目标与变化":"从复仇者成长为守护者"}',
                     "主角，悟道突破，寿元透支", "主角,剑修")).lastrowid
    db.execute("INSERT INTO entities(work_id, category, name, fields_json, content, tags) VALUES (?,?,?,?,?,?)",
               (work_id, "character", "陆清雪",
                '{"身份":"天剑宗同门师姐","性格":"冷静克制","背景":"舍身护法，剑心受创","目标与变化":""}',
                "同门师姐，对叶临渊暗生情愫", "支援,剑修"))
    db.execute("INSERT INTO entities(work_id, category, name, fields_json, content, tags) VALUES (?,?,?,?,?,?)",
               (work_id, "place", "天剑宗", "{}", "悬于通天峰巅的古老剑宗，镇守着玄冥裂隙的第一道封印。", "宗门,主场景"))
    db.execute("INSERT INTO entities(work_id, category, name, fields_json, content, tags) VALUES (?,?,?,?,?,?)",
               (work_id, "item", "龙渊剑", "{}", "凡铁铸就的古剑，内蕴祖师一缕剑意，可引九天罡风。", "关键道具"))
    db.execute("INSERT INTO chapter_entities(chapter_id, entity_id) VALUES (?,?)", (c1, e1))

    # 伏笔（统一委托 asset_hub）
    from app.services.asset_hub import upsert_foreshadow
    upsert_foreshadow(db, work_id, "传讯符灰烬", "大长老袖袍中的传讯符悄然化为灰烬，魔道暗影潜伏的暗线被无声埋下。", "planted", c1, node1)
    upsert_foreshadow(db, work_id, "剑阁旧印裂痕", "剑阁旧印上的裂痕指向三十年前的心魔折断之谜。", "pending", c2, node2)


    db.commit()
    return {"ok": True, "work_id": work_id, "message": "示例作品《太虚仙途》已创建"}
