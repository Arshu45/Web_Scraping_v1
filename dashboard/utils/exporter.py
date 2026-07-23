"""
Exporter utility — generates Excel workbook from filtered promotions DataFrame.
"""
import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def export_to_excel(df: pd.DataFrame) -> bytes:
    """
    Exports the filtered promotions DataFrame to an Excel spreadsheet in the
    exact Weekly Competitor Matrix format shown on the Streamlit dashboard.
    
    Layout:
    - Grouped by Category.
    - Category name acts as a section header row.
    - Grid columns: Brand (first column), Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday.
    - Cell contents contain newline-separated promotion titles.
    - Soft styling matching the dashboard's design tokens.
    """
    if df.empty:
        wb = Workbook()
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
        
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    matrix_df = df.copy()
    matrix_df["Day"] = matrix_df["scraped_at"].dt.day_name()
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Weekly Competitor Matrix"
    
    # Ensure grid lines are explicitly visible
    ws.views.sheetView[0].showGridLines = True
    
    # Define design colors and styles matching styles.py
    # Category Header Banner Style
    cat_fill = PatternFill(start_color="EEF0F8", end_color="EEF0F8", fill_type="solid")
    cat_font = Font(name="Segoe UI", size=11, bold=True, color="303247")
    
    # Table Column Header Style
    header_fill = PatternFill(start_color="F4F4F8", end_color="F4F4F8", fill_type="solid")
    header_font = Font(name="Segoe UI", size=10, bold=True, color="505060")
    
    # Row Headers (Brand Names) and Data Cells
    brand_font = Font(name="Segoe UI", size=10, bold=True, color="1A1A2E")
    data_font = Font(name="Segoe UI", size=10, bold=False, color="1A1A2E")
    
    # Soft borders
    border_side = Side(border_style="thin", color="E5E5EE")
    cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
    
    # Alignments
    align_left_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)
    align_center = Alignment(horizontal="center", vertical="center")
    
    current_row = 1
    
    # Group and build matrices for each unique category
    categories = sorted(matrix_df["category"].dropna().unique())
    for category in categories:
        cat_df = matrix_df[matrix_df["category"] == category]
        if cat_df.empty:
            continue
            
        # Group duplicates and join with newlines
        grouped = (
            cat_df.groupby(["brand", "Day"])["offer_title"]
            .apply(lambda values: "\n".join(dict.fromkeys(v for v in values if isinstance(v, str) and v.strip())))
            .reset_index()
        )
        matrix = grouped.pivot(index="brand", columns="Day", values="offer_title")
        matrix = matrix.reindex(columns=weekday_order).fillna("")
        matrix = matrix.reset_index().rename(columns={"brand": category})
        
        # 1. Write Category Title Block (Merged Row)
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
        cat_cell = ws.cell(row=current_row, column=1)
        cat_cell.value = f" {category.upper()}"
        cat_cell.font = cat_font
        cat_cell.fill = cat_fill
        cat_cell.alignment = Alignment(horizontal="left", vertical="center")
        
        for c in range(1, 9):
            ws.cell(row=current_row, column=c).border = cell_border
            ws.cell(row=current_row, column=c).fill = cat_fill
            
        ws.row_dimensions[current_row].height = 28
        current_row += 1
        
        # 2. Write Weekday Column Headers
        headers = [category] + weekday_order
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center if col_idx > 1 else align_left_wrap
            cell.border = cell_border
            
        ws.row_dimensions[current_row].height = 22
        current_row += 1
        
        # 3. Write Matrix Data Rows
        for _, row in matrix.iterrows():
            # Brand Name cell
            brand_cell = ws.cell(row=current_row, column=1)
            brand_cell.value = row[category]
            brand_cell.font = brand_font
            brand_cell.alignment = align_left_wrap
            brand_cell.border = cell_border
            
            # Days of the Week cells
            max_lines = 1
            for d_idx, day in enumerate(weekday_order, start=2):
                cell = ws.cell(row=current_row, column=d_idx)
                cell_value = row[day]
                cell.value = cell_value
                cell.font = data_font
                cell.alignment = align_left_wrap
                cell.border = cell_border
                
                # Check line counts to calculate row height
                lines = len(cell_value.split('\n'))
                if lines > max_lines:
                    max_lines = lines
            
            # Set dynamic row height to fit wrapped text
            ws.row_dimensions[current_row].height = max(max_lines * 15 + 10, 30)
            current_row += 1
            
        # Spacing row after matrix table
        current_row += 1
        ws.row_dimensions[current_row].height = 15
        current_row += 1
        
    # Auto-adjust column widths
    ws.column_dimensions['A'].width = 22
    for c in ['B', 'C', 'D', 'E', 'F', 'G', 'H']:
        ws.column_dimensions[c].width = 30
        
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
