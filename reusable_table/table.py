from django.template import Template, Context
from django.template.loader import get_template
from django.core.paginator import Paginator, InvalidPage
from django.http import HttpResponse, HttpResponseRedirect

pagination_size_default = 10

formats = ["csv",]
try:
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    from reportlab.platypus import Table as PDFTable
    from reportlab.platypus import TableStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib import colors 
    formats.append("pdf")
except ImportError:
    pass
    

import os
import csv
import StringIO

from tempfile import mkstemp
from datetime import datetime

path = os.path.join(os.path.dirname(__file__), "templates")

def paginate(queryset, number, size=pagination_size_default):
    pages = Paginator(queryset, pagination_size_default)
    result = { "pages": pages, "count": queryset.count(), "jump": jump(pages, number) }
    if pages.num_pages > 1:
        result["paginated"] = True
    else:
        result["paginated"] = False
    try:
        result["page"] = pages.page(number)
    except InvalidPage:
        # no page, go to 1
        result["page"] = pages.page(1)
    return result

def jump(pages, index):
    res = { "start_ellipsis": False, "end_ellipsis": False }
    nums = pages.page_range
    side = 5
    index -= 1
    start = index - side
    if start > 0:
        res["start_ellipsis"] = True
        
    if start < 0:
        start = 0
        
    end = index + side + 1
    if end > (len(nums) + 1):
        res["pages_bit"] = nums[start:]        
    else:
        res["pages_bit"] = nums[start:end]
        res["end_ellipsis"] = True
        
    return res

class Table:
    def __init__(self, model, fields):
        self.model = model
        results = []
        for head, column, bit in fields:
            results.append({"name": head, "column":column, "bit":bit})
        self.fields = results
        self.template_wrapper = Template(open(os.path.join(path, "table_wrapper.html")).read())
        self.html_second_column = open(os.path.join(path, "html_second_column.html")).read()
        self.html_first_column = open(os.path.join(path, "html_first_column.html")).read()
    
    def __call__(self, request, key, queryset):
        self.key = key
        format = request.GET.get("format_%s" % self.key, "html") 
        method = getattr(self, "handle_%s" % format, None)
        queryset = self.model.objects.filter(queryset)
        if method:
            return format, method(request, queryset)
        else:
            raise NotImplementedError, "The format: %s is not handled" % format
    
    def handle_csv(self, request, queryset):
        output = StringIO.StringIO()
        csvio = csv.writer(output)
        header = False
        for row in queryset:
            ctx = Context({"object": row })
            if not header:
                csvio.writerow([f["name"] for f in self.fields])
                header = True
            values = [ Template(h["bit"]).render(ctx) for h in self.fields ]
            csvio.writerow(values)

        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = 'attachment; filename=report.csv'    
        response.write(output.getvalue())
        return response
        
    def handle_pdf(self, request, queryset):
        if "pdf" not in formats:
            raise ImportError, "The site is not configured to handle pdf."
    
        # this is again some quick and dirty sample code    
        elements = []
        styles = getSampleStyleSheet()
        styles['Title'].alignment = TA_LEFT
        styles['Title'].fontName = styles['Heading2'].fontName = "Helvetica"
        styles["Normal"].fontName = "Helvetica"
        filename = mkstemp(".pdf")[-1]
        doc = SimpleDocTemplate(filename)

        elements.append(Paragraph("MCTC", styles['Title']))
        elements.append(Paragraph("%s List" % self.model.__name__, styles['Heading2']))        

        data = []
        header = False
        for row in queryset:
            if not header:
                data.append([f["name"] for f in self.fields])
                header = True
            ctx = Context({"object": row })
            values = [ Template(h["bit"]).render(ctx) for h in self.fields ]
            data.append(values)

        table = PDFTable(data)
        table.setStyle(TableStyle([
            ('ALIGNMENT', (0,0), (-1,-1), 'LEFT'),
            ('LINEBELOW', (0,0), (-1,-0), 2, colors.black),            
            ('LINEBELOW', (0,1), (-1,-1), 0.8, colors.lightgrey),
            ('FONT', (0,0), (-1, -1), "Helvetica"),
            ('ROWBACKGROUNDS', (0,0), (-1, -1), [colors.whitesmoke, colors.white]),
        ]))        
        elements.append(table)
        elements.append(Paragraph("Created: %s" % datetime.now().strftime("%d/%m/%Y"), styles["Normal"]))        
        doc.build(elements)

        response = HttpResponse(mimetype='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=report.pdf'
        response.write(open(filename).read())
        os.remove(filename)
        return response
    
    def handle_html(self, request, queryset):
        # get the default page number
        default = request.GET.get("page_%s" % self.key, 1)
        try:
            default = int(default)
        except (TypeError, ValueError):
            default = 1
        
        for h in self.fields:
            column = h["column"]
            sort_key = "sort_%s_%s" % (self.key, column)
            value = request.GET.get(sort_key, None)
            h["asc"] = True            
            if value == "asc":
                queryset = queryset.order_by(column)
                break
            elif value == "desc":
                queryset = queryset.order_by("-%s" % column)
                h["asc"] = False
                break        
            
        paginated = paginate(queryset, default)
        rows = []
        for row in paginated["page"].object_list:
            ctx = Context({"object": row})
            build = []
            first = hasattr(row, "get_absolute_url") and True or False
            for h in self.fields:
                if first:
                    bit = self.html_first_column % (
                        row.get_absolute_url(), 
                        Template(h["bit"]).render(ctx)
                        )
                    first = False
                else:
                    bit = self.html_second_column % (
                        Template(h["bit"]).render(ctx)
                        )
                build.append(bit)
            
            rows.append("".join(build))
        self.context = {
            "columns": self.fields,
            "rows": rows,
            "object_list": paginated,
            "table_key": self.key,
            "formats": formats
        }
        return self.template_wrapper.render(Context(self.context))

tables = {}
def register(name, model, fields):
    global tables
    for field in fields: assert len(field) == 3
    tables[name] = Table(model, fields)
    
def get(request, tabs):
    result = []
    nonhtml = None
    x = 1
    for name, query in tabs:
        format, tab = tables[name](request, str(x), query)
        if not nonhtml and format != "html":
            nonhtml = tab
        result.append(tab)
        x += 1

    return nonhtml, result