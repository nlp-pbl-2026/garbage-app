"""Official HTML area/rule extraction, independent of calendar image icons."""

from datetime import date, timedelta
import re

from uwajima_html import Document, expanded

WEEKDAYS = {c: i for i, c in enumerate("月火水木金土日")}
REGIONS = {
    "uwajima": "宇和島地区",
    "yoshida": "吉田地区",
    "mima": "三間地区",
    "tsushima": "津島地区",
}


def matches(day, rule):
    rule = rule.replace("\u200b", "")
    weekdays = [WEEKDAYS[c] for c in re.findall(r"([月火水木金土日])曜日", rule)]
    if not weekdays or day.weekday() not in weekdays:
        return False
    if "第" in rule:
        ordinal = (day.day - 1) // 7 + 1
        return str(ordinal) in re.findall(r"[1-5]", rule)
    return True


def dates():
    day = date(2026, 4, 1)
    while day <= date(2027, 3, 31):
        yield day
        day += timedelta(days=1)


def areas(data):
    result = []
    for region in REGIONS:
        page = data / "source" / f"calendar-{region}.html"
        tables = [
            expanded(t)
            for t in Document(
                page.read_text(), "https://www.city.uwajima.ehime.jp/"
            ).tables
        ]
        records = []
        for row in tables[0][2 if region == "uwajima" else 1 :]:
            groups = [row[1:5], row[5:9]] if region == "uwajima" else [row]
            for group in groups:
                if not group or not group[0]["text"]:
                    continue
                name = re.sub(r"\s*\[PDF.*", "", group[0]["text"]).strip().lstrip("※")
                if (
                    not group[0]["links"]
                    and region == "uwajima"
                    and not any(i in name for i in ["戸島", "日振島"])
                ):
                    continue
                if any(r["name"] == name for r in records):
                    continue  # explicit rowspan of the same island row (PET/month-end)
                texts = [g["text"].replace("\u200b", "") for g in group[1:]]
                if region == "uwajima":
                    rules = dict(
                        burnable=texts[0],
                        non_burnable=texts[1],
                        bottles_cans=texts[2],
                        pet=texts[1],
                    )
                    if not group[0]["links"]:
                        rules["pet"] = "月末（実日付未確認）"
                elif region == "mima":
                    rules = dict(
                        burnable=texts[0],
                        non_burnable=texts[1],
                        bottles_cans=texts[1],
                        pet=texts[2],
                    )
                elif region == "tsushima":
                    rules = dict(
                        burnable=texts[0],
                        non_burnable="第2・4水曜日",
                        bottles_cans="第1・3・5水曜日",
                        pet=texts[3],
                        paper=texts[4],
                    )
                else:
                    rules = dict(
                        zip(["burnable", "non_burnable", "bottles_cans", "pet"], texts)
                    )
                url = group[0]["links"][0]["url"] if group[0]["links"] else None
                records.append(dict(region=region, name=name, pdf_url=url, rules=rules))
        if region == "yoshida":
            paper = {r[0]["text"]: r[1]["text"] for r in tables[1][1:]}
            for r in records:
                if r["name"] in paper:
                    r["rules"]["paper"] = paper[r["name"]]
        if region == "mima":
            # The two official tables have different boundaries; intersect their
            # explicitly listed settlements, never assign by a nearby name.
            split = []
            for record in records:
                settlements = set(record["name"].split("、"))
                for row in tables[1][1:]:
                    names = [n for n in row[0]["text"].split("、") if n in settlements]
                    if names:
                        split.append(
                            record
                            | dict(
                                name="、".join(names),
                                rules=record["rules"] | {"paper": row[1]["text"]},
                            )
                        )
            if set(n for r in split for n in r["name"].split("、")) != set(
                n for r in records for n in r["name"].split("、")
            ):
                raise ValueError("Mima settlement mapping mismatch")
            records = split
        if region == "tsushima":
            row = tables[1][1]
            records.append(
                dict(
                    region=region,
                    name=row[0]["text"],
                    pdf_url=None,
                    rules=dict(
                        burnable="金曜日",
                        non_burnable="第1金曜日",
                        bottles_cans="第1金曜日",
                        pet="第1金曜日",
                        paper="第1金曜日",
                    ),
                )
            )
        result.extend(records)
    if len({(r["region"], r["name"]) for r in result}) != len(result):
        raise ValueError("Duplicate selected area")
    return result
