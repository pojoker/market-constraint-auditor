#!/usr/bin/env python3
"""每日报告邮件投递（2026-07-22 增设）。

诊断成功后由 ~/bin/market-auditor-diagnose.sh 第 6b 步调用（best-effort）：
把 reports/ 下最新的 PDF 发到配置的收件箱，正文附报告 markdown 开头摘要。

凭据放 ~/.market-auditor-mail.json（chmod 600，不入 git）：
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 465,
  "user": "you@gmail.com",
  "app_password": "<Google 应用专用密码，16 位>",
  "to": "you@gmail.com"
}

幂等：已发过的文件记录在 data/mail_sent.txt，重复调用不会重发。
用法：send_report_mail.py [--dry-run] [--report <pdf路径>]
"""
import argparse
import json
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports"
SENT_LOG = REPO / "data" / "mail_sent.txt"
CONFIG = Path.home() / ".market-auditor-mail.json"


def load_config():
    if not CONFIG.exists():
        return None, f"config missing: {CONFIG}"
    try:
        cfg = json.loads(CONFIG.read_text())
    except Exception as e:
        return None, f"config unreadable: {e}"
    required = ["smtp_host", "smtp_port", "user", "app_password", "to"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        return None, f"config incomplete, missing: {missing}"
    if "<" in str(cfg.get("app_password", "")):
        return None, "config still has placeholder app_password"
    return cfg, None


def latest_pdf():
    pdfs = sorted(REPORTS.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
    return pdfs[-1] if pdfs else None


def already_sent(name):
    if not SENT_LOG.exists():
        return False
    return name in SENT_LOG.read_text().splitlines()


def mark_sent(name):
    with open(SENT_LOG, "a") as f:
        f.write(name + "\n")


def body_from_md(pdf_path):
    md = pdf_path.with_suffix(".md")
    if not md.exists():
        return f"附件：{pdf_path.name}"
    text = md.read_text(errors="replace")
    head = text[:1500]
    if len(text) > 1500:
        head += "\n\n……（全文见附件 PDF）"
    return head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只检查配置与选件，不发送")
    ap.add_argument("--report", help="指定要发送的 PDF 路径（默认取 reports/ 最新）")
    args = ap.parse_args()

    cfg, err = load_config()
    if err:
        print(f"SKIP mail: {err}")
        return 0  # 配置未就绪不算失败——wrapper 里 best-effort

    pdf = Path(args.report) if args.report else latest_pdf()
    if not pdf or not pdf.exists():
        print("SKIP mail: no pdf found")
        return 0
    if already_sent(pdf.name) and not args.report:
        print(f"SKIP mail: already sent {pdf.name}")
        return 0

    msg = EmailMessage()
    msg["Subject"] = f"市场约束诊断 · {pdf.stem}"
    msg["From"] = cfg["user"]
    msg["To"] = cfg["to"]
    msg.set_content(body_from_md(pdf))
    msg.add_attachment(
        pdf.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf.name,
    )

    if args.dry_run:
        print(f"DRY-RUN: would send {pdf.name} ({pdf.stat().st_size // 1024} KB) "
              f"to {cfg['to']} via {cfg['smtp_host']}:{cfg['smtp_port']}")
        return 0

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["smtp_host"], int(cfg["smtp_port"]),
                              context=ctx, timeout=30) as s:
            s.login(cfg["user"], cfg["app_password"])
            s.send_message(msg)
    except Exception as e:
        print(f"FAIL mail: {type(e).__name__}: {e}")
        return 1

    mark_sent(pdf.name)
    print(f"SENT {pdf.name} -> {cfg['to']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
