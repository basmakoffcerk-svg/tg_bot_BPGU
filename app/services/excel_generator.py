"""
Генератор официальной рапортички посещаемости в формате Microsoft Excel (.xlsx) через openpyxl.
Соответствует факультетскому стандарту БГПУ.
"""
from datetime import date
from io import BytesIO
from typing import Dict, List

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models import STATUS_ABSENT_EXCUSED, STATUS_ABSENT_UNEXCUSED, STATUS_LATE, STATUS_MANUAL_CONFIRM, STATUS_PRESENT


def generate_dean_report_xlsx(
    group_name: str,
    university_name: str,
    date_from: date,
    date_to: date,
    students: List[dict],
    dates_and_pairs: List[tuple[date, int, str]],  # (calendar_date, pair_number, subject_short)
    attendance_matrix: Dict[tuple[int, date, int], str],  # (student_id, date, pair_number) -> status
) -> bytes:
    """
    Генерирует бинарный поток .xlsx с рапортичкой.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Рапортичка"

    # Стили
    font_header_bold = Font(name="Calibri", size=11, bold=True)
    font_regular = Font(name="Calibri", size=10)
    font_bold = Font(name="Calibri", size=10, bold=True)
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    
    thin_border_side = Side(border_style="thin", color="000000")
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    thick_bottom_side = Side(border_style="medium", color="000000")
    
    fill_header = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    fill_absent = PatternFill(start_color="FFD9D9", end_color="FFD9D9", fill_type="solid")  # Неуважительный (Н)
    fill_excused = PatternFill(start_color="E8D5F5", end_color="E8D5F5", fill_type="solid")  # Уважительный (У)
    fill_late = PatternFill(start_color="D6EAF8", end_color="D6EAF8", fill_type="solid")     # Опоздал (О)

    # 1. Шапка документа
    ws.merge_cells("A1:M1")
    ws["A1"] = f"{university_name} — РАПОРТИЧКА УЧЕТА ПОСЕЩАЕМОСТИ"
    ws["A1"].font = Font(name="Calibri", size=13, bold=True)
    ws["A1"].alignment = align_center

    ws.merge_cells("A2:M2")
    ws["A2"] = f"Академическая группа: {group_name} | Период: {date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"
    ws["A2"].font = font_header_bold
    ws["A2"].alignment = align_center

    # 2. Табличная шапка
    start_row = 4
    ws.cell(row=start_row, column=1, value="№").font = font_bold
    ws.cell(row=start_row, column=1).alignment = align_center
    ws.cell(row=start_row, column=1).fill = fill_header
    ws.cell(row=start_row, column=1).border = thin_border

    ws.cell(row=start_row, column=2, value="ФИО Студента").font = font_bold
    ws.cell(row=start_row, column=2).alignment = align_center
    ws.cell(row=start_row, column=2).fill = fill_header
    ws.cell(row=start_row, column=2).border = thin_border

    ws.cell(row=start_row, column=3, value="Подгр.").font = font_bold
    ws.cell(row=start_row, column=3).alignment = align_center
    ws.cell(row=start_row, column=3).fill = fill_header
    ws.cell(row=start_row, column=3).border = thin_border

    col_idx = 4
    pair_columns: List[tuple[date, int, int]] = []  # (calendar_date, pair_number, col_idx)

    for c_date, pair_num, subj in dates_and_pairs:
        cell = ws.cell(row=start_row, column=col_idx, value=f"{c_date.strftime('%d.%m')}\n№{pair_num}")
        cell.font = Font(name="Calibri", size=9, bold=True)
        cell.alignment = align_center
        cell.fill = fill_header
        cell.border = thin_border
        pair_columns.append((c_date, pair_num, col_idx))
        col_idx += 1

    # Сводные колонки
    summary_cols = [
        ("Пропущено (Н), ч", "absent_unexcused_hours"),
        ("Уваж. (У), ч", "absent_excused_hours"),
        ("Всего часов", "total_absent_hours"),
    ]
    summary_col_indices: Dict[str, int] = {}

    for title, key in summary_cols:
        cell = ws.cell(row=start_row, column=col_idx, value=title)
        cell.font = font_bold
        cell.alignment = align_center
        cell.fill = fill_header
        cell.border = thin_border
        summary_col_indices[key] = col_idx
        col_idx += 1

    # 3. Заполнение строк студентов (по алфавиту)
    current_row = start_row + 1
    sorted_students = sorted(students, key=lambda s: s["full_name"])

    for idx, student in enumerate(sorted_students, start=1):
        ws.cell(row=current_row, column=1, value=idx).alignment = align_center
        ws.cell(row=current_row, column=1).border = thin_border
        ws.cell(row=current_row, column=1).font = font_regular

        ws.cell(row=current_row, column=2, value=student["full_name"]).alignment = align_left
        ws.cell(row=current_row, column=2).border = thin_border
        ws.cell(row=current_row, column=2).font = font_regular

        ws.cell(row=current_row, column=3, value=student["subgroup"]).alignment = align_center
        ws.cell(row=current_row, column=3).border = thin_border
        ws.cell(row=current_row, column=3).font = font_regular

        student_unexcused_pairs = 0
        student_excused_pairs = 0

        for c_date, pair_num, col in pair_columns:
            st = attendance_matrix.get((student["id"], c_date, pair_num), STATUS_ABSENT_UNEXCUSED)
            cell = ws.cell(row=current_row, column=col)
            cell.border = thin_border
            cell.alignment = align_center
            cell.font = font_bold

            if st in (STATUS_PRESENT, STATUS_MANUAL_CONFIRM):
                cell.value = "·"
            elif st == STATUS_ABSENT_EXCUSED:
                cell.value = "У"
                cell.fill = fill_excused
                student_excused_pairs += 1
            elif st == STATUS_LATE:
                cell.value = "О"
                cell.fill = fill_late
            else:
                cell.value = "Н"
                cell.fill = fill_absent
                student_unexcused_pairs += 1

        # Подсчет часов (1 пара = 2 часа)
        unexcused_hours = student_unexcused_pairs * 2
        excused_hours = student_excused_pairs * 2
        total_hours = unexcused_hours + excused_hours

        cell_un = ws.cell(row=current_row, column=summary_col_indices["absent_unexcused_hours"], value=unexcused_hours)
        cell_un.alignment = align_center
        cell_un.border = thin_border
        cell_un.font = font_bold

        cell_ex = ws.cell(row=current_row, column=summary_col_indices["absent_excused_hours"], value=excused_hours)
        cell_ex.alignment = align_center
        cell_ex.border = thin_border
        cell_ex.font = font_regular

        cell_tot = ws.cell(row=current_row, column=summary_col_indices["total_absent_hours"], value=total_hours)
        cell_tot.alignment = align_center
        cell_tot.border = thin_border
        cell_tot.font = font_bold

        current_row += 1

    # 4. Итоговая строка
    ws.cell(row=current_row, column=1, value="").border = thin_border
    ws.merge_cells(start_row=current_row, start_column=2, end_row=current_row, end_column=3)
    tot_label = ws.cell(row=current_row, column=2, value="ИТОГО ПРОПУЩЕНО ЧАСОВ ПО ГРУППЕ:")
    tot_label.font = font_bold
    tot_label.alignment = Alignment(horizontal="right", vertical="center")
    tot_label.border = thin_border
    ws.cell(row=current_row, column=3).border = thin_border

    for _, _, col in pair_columns:
        ws.cell(row=current_row, column=col, value="").border = thin_border

    start_data_row = start_row + 1
    end_data_row = current_row - 1

    for key in ["absent_unexcused_hours", "absent_excused_hours", "total_absent_hours"]:
        col = summary_col_indices[key]
        col_letter = get_column_letter(col)
        cell = ws.cell(row=current_row, column=col, value=f"=SUM({col_letter}{start_data_row}:{col_letter}{end_data_row})")
        cell.font = font_bold
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = fill_header

    # Автоподгонка ширины колонок
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 8
    for _, _, col in pair_columns:
        ws.column_dimensions[get_column_letter(col)].width = 7
    for key in summary_col_indices:
        ws.column_dimensions[get_column_letter(summary_col_indices[key])].width = 15

    output = BytesIO()
    wb.save(output)
    return output.getvalue()
