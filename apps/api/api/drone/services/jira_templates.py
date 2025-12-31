# =============================================================================
# 모듈 설명: Drone SOP Jira 템플릿 HTML 소스를 코드로 제공합니다.
# - 주요 대상: TEMPLATE_SOURCES
# - 불변 조건: 템플릿 키는 line_a/line_b 등 고정 키를 사용합니다.
# =============================================================================

"""Drone SOP Jira 템플릿 소스 모음.

- 주요 대상: TEMPLATE_SOURCES
- 주요 엔드포인트/클래스: 없음(상수만 제공)
- 가정/불변 조건: 템플릿 키는 사전에 정의된 문자열이어야 함
"""
from __future__ import annotations

LINE_A_TEMPLATE = """<div>
  <div style="margin:8px 0;">
    <table style="border:1px solid #ccc; border-collapse:collapse; width:auto;">
      <caption style="caption-side:bottom; text-align:right; font-size:11px; color:#888; margin:0; padding:0;">
        SOP by : {{ knoxid|default:"-" }} ({{ user_sdwt_prod|default:"-" }})
      </caption>
      <thead>
        <tr>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">Step_seq</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">PPID</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">EQP_CB</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">Lot_id</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ main_step|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ ppid|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ eqp_cb|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ lot_id|default:"-" }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div style="margin:4px 0;">
    <div style="font-size:14px;">
      📄 CTTTM URL :
      {% if ctttm_urls %}
        {% for item in ctttm_urls %}
          <a href="{{ item.url }}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{{ item.label }}</a>{% if not forloop.last %},{% endif %}
        {% endfor %}
      {% else %}
        <span style="font-size:14px; color:#999;">-</span>
      {% endif %}
    </div>
  </div>

  <div style="margin:4px 0;">
    <div style="font-size:14px; margin-top:12px;">
      💿 Defect URL :
      {% if defect_url %}
        <a href="{{ defect_url }}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{{ lot_id|default:"-" }}</a>
      {% else %}
        <span style="font-size:14px; color:#999;">-</span>
      {% endif %}
    </div>
  </div>

  {% if comment_raw %}
    <div style="margin:4px 0;">
      <div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">🎨 Comment : {{ comment_raw }}</div>
      <div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">💬 답변  :&nbsp; </div>
    </div>
  {% endif %}
</div>
"""

LINE_B_TEMPLATE = """<div>
  <div style="margin:8px 0;">
    <table style="border:1px solid #ccc; border-collapse:collapse; width:auto;">
      <caption style="caption-side:bottom; text-align:right; font-size:11px; color:#888; margin:0; padding:0;">
        SOP by : {{ knoxid|default:"-" }} ({{ user_sdwt_prod|default:"-" }})
      </caption>
      <thead>
        <tr>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">Step_seq</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">PPID</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">EQP_CB</th>
          <th style="border:1px solid #ccc; background-color:#F2F2F2; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:12px;">Lot_id</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ main_step|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ ppid|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ eqp_cb|default:"-" }}</td>
          <td style="border:1px solid #ccc; text-align:center; padding:4px; padding-left:8px; padding-right:8px; font-size:14px;">{{ lot_id|default:"-" }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div style="margin:4px 0;">
    <div style="font-size:14px;">
      📄 CTTTM URL :
      {% if ctttm_urls %}
        {% for item in ctttm_urls %}
          <a href="{{ item.url }}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{{ item.label }}</a>{% if not forloop.last %},{% endif %}
        {% endfor %}
      {% else %}
        <span style="font-size:14px; color:#999;">-</span>
      {% endif %}
    </div>
  </div>

  <div style="margin:4px 0;">
    <div style="font-size:14px; margin-top:12px;">
      💿 Defect URL :
      {% if defect_url %}
        <a href="{{ defect_url }}" target="_blank" rel="noopener noreferrer" style="font-size:14px;">{{ lot_id|default:"-" }}</a>
      {% else %}
        <span style="font-size:14px; color:#999;">-</span>
      {% endif %}
    </div>
  </div>

  {% if comment_raw %}
    <div style="margin:4px 0;">
      <div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">🎨 Comment : {{ comment_raw }}</div>
      <div style="font-size:14px; margin-top:12px; white-space:pre-wrap;">💬 답변  :&nbsp; </div>
    </div>
  {% endif %}
</div>
"""

TEMPLATE_SOURCES = {
    "line_a": LINE_A_TEMPLATE,
    "line_b": LINE_B_TEMPLATE,
}

__all__ = ["TEMPLATE_SOURCES"]
