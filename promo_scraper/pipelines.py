import os
from scrapy.exporters import JsonItemExporter

class BrandJSONPipeline:
    def __init__(self):
        self.files = {}
        self.exporters = {}

    def open_spider(self, spider):
        os.makedirs('data', exist_ok=True)

    def process_item(self, item, spider):
        brand = item.get('brand', 'unknown').lower()
        source = item.get('source', 'unknown').lower()
        
        file_key = f"{source}_{brand}"
        
        if file_key not in self.files:
            file_path = os.path.join('data', f"{file_key}_offers.json")
            self.files[file_key] = open(file_path, 'wb')
            exporter = JsonItemExporter(
                self.files[file_key], 
                encoding='utf-8', 
                ensure_ascii=False, 
                indent=4
            )
            exporter.start_exporting()
            self.exporters[file_key] = exporter
            
        self.exporters[file_key].export_item(item)
        return item

    def close_spider(self, spider):
        for exporter in self.exporters.values():
            exporter.finish_exporting()
        for f in self.files.values():
            f.close()
