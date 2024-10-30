import os
import subprocess
import zipfile
import shutil
import json
import requests
import platform
from pathlib import Path
import pcbnew  # Import KiCad's PCB module
import wx
import traceback

class KiCadTool(wx.Frame):
    def __init__(self, parent, title):
        super(KiCadTool, self).__init__(parent, title=title, size=(600, 500))
        self.pcb_file = ''
        self.schematic_file = ''
        self.pcba_number = ''
        self.revision = ''
        self.drawing_sheet_path = None
        self.theme_path = None
        self.kicad_cli = self.locate_kicad_cli()

        # Dokuly settings
        self.dokuly_api_key = ""
        self.dokuly_tenant = ""
        self.dokuly_url = ""
        self.url_protocol = ""
        self.dokuly_base_api_url = ""
        self.overwrite_files = False

        self.pcba_pk = -1

        # Fetching
        self.fetch_pcba_url = ""

        # Uploading
        self.file_upload_pcba_url = ""
        self.bom_upload_url = ""
        self.thumbnail_upload_url = ""
        
        self.temp_file_path = None

        self.initUI()
        self.Centre()
        self.Show()

    # Need to update the URLs after fetching the PCBA item as pk is -1 initially
    def update_pcba_urls(self):
        self.file_upload_pcba_url = f"{self.dokuly_base_api_url}/api/v1/pcbas/upload/{self.pcba_pk}/"
        self.bom_upload_url = f"{self.dokuly_base_api_url}/api/v1/pcbas/bom/{self.pcba_pk}/"
        self.thumbnail_upload_url = f"{self.dokuly_base_api_url}/api/v1/pcbas/thumbnail/{self.pcba_pk}/"
        self.fetch_pcba_url = f"{self.dokuly_base_api_url}/api/v1/pcbas/fetchByPartNumberRevision/"


    def locate_kicad_cli(self):
        # Attempt to locate kicad-cli in common installation paths
        if platform.system() == 'Windows':
            default_path = r'C:\Program Files\KiCad\8.0\bin\kicad-cli.exe'
        elif platform.system() == 'Darwin':  # macOS
            default_path = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
        else:  # Linux
            default_path = '/usr/bin/kicad-cli'

        if os.path.exists(default_path):
            return default_path
        else:
            return 'kicad-cli'  # Assumes kicad-cli is in PATH
        

    def initUI(self):
        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # Label to show selected PCB file
        self.label = wx.StaticText(panel, label='No PCB file selected.')
        vbox.Add(self.label, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Display PCBA_NUMBER and REVISION
        name_box = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(panel, label='PCBA_NUMBER:')
        self.pcba_number_value = wx.StaticText(panel, label='')
        name_box.Add(name_label, flag=wx.RIGHT, border=8)
        name_box.Add(self.pcba_number_value, proportion=1)
        vbox.Add(name_box, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        revision_box = wx.BoxSizer(wx.HORIZONTAL)
        revision_label = wx.StaticText(panel, label='REVISION:')
        self.revision_value = wx.StaticText(panel, label='')
        revision_box.Add(revision_label, flag=wx.RIGHT, border=8)
        revision_box.Add(self.revision_value, proportion=1)
        vbox.Add(revision_box, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

       # Button to Sync PCBA to dokuly
        sync_button = wx.Button(panel, label='Push PCBA to dokuly')
        sync_button.Bind(wx.EVT_BUTTON, self.push_pcba_to_dokuly)
        vbox.Add(sync_button, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Text area to display output
        self.output_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        vbox.Add(self.output_text, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        panel.SetSizer(vbox)

        self.load_env_file()

        self.dokuly_base_api_url = self.get_dokuly_base_api_url()

        # Get the currently open PCB file
        self.get_current_pcb_file()

        # Get PCBA_NUMBER and REVISION from board variables
        self.populate_board_variables()

        self.update_pcba_urls()

        # Fetch PCBA item from dokuly
        self.fetch_pcba_item()

        self.generate_temp_file_folder()


    def print_output(self, message):
        self.output_text.AppendText(message)

    
    def generate_temp_file_folder(self):
        plugin_dir = os.path.dirname(__file__)
        temp_folder = os.path.join(plugin_dir, 'temp')
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)

        self.temp_file_path = temp_folder


    def get_current_pcb_file(self):
        board = pcbnew.GetBoard()
        if board is not None:
            self.pcb_file = board.GetFileName()
            if self.pcb_file:
                self.label.SetLabel(f'Selected PCB file: {os.path.basename(self.pcb_file)}')

                # try to find the schematic file
                project_dir = os.path.dirname(self.pcb_file)
                project_name = os.path.splitext(os.path.basename(self.pcb_file))[0]
                self.schematic_file = os.path.join(project_dir, f"{project_name}.kicad_sch")
                if os.path.exists(self.schematic_file):
                    self.print_output(f"Schematic file found: {self.schematic_file}\n")
                else:
                    self.print_output(f"Schematic file not found: {self.schematic_file}\n")
                    self.schematic_file = ''  # reset if not found
            else:
                self.label.SetLabel('No PCB file selected.')
        else:
            self.label.SetLabel('No PCB file selected.')
            

    def populate_board_variables(self):
        board = pcbnew.GetBoard()
        if board is not None:
            # Get board variables (text variables)
            variables = board.GetProperties()
            # Access variables using key lookup
            self.pcba_number = variables['PCBA_NUMBER'] if 'PCBA_NUMBER' in variables else ''
            self.revision = variables['PART_REVISION'] if 'PART_REVISION' in variables else ''

            self.pcba_number_value.SetLabel(self.pcba_number)
            self.revision_value.SetLabel(self.revision)
        
        else:
            self.print_output('\nUnable to access board variables.\n')


    def push_pcba_to_dokuly(self, event):
        if not self.pcba_number or not self.revision:
            self.print_output('\nPCBA_NUMBER or REVISION is not set in board variables.\n')
            return
        
        if not self.dokuly_api_key:
            self.print_output('\nError: DOKULY_API_KEY environment variable is not set.\n')
            return
        
        self.print_output('\n\nPushing PCBA to dokuly... PLEASE WAIT UNTIL UPLOAD IS COMPLETED; DO NOT CLOSE OR RETRY.\n\n')
        
        try:
            pcb_front_pdf_file_path, pcb_back_pdf_file_path = self.generate_pcb_pdf()
            if pcb_front_pdf_file_path and pcb_back_pdf_file_path:
                self.upload_pcb_pdf(pcb_front_pdf_file_path, pcb_back_pdf_file_path)
            else:
                self.print_output('\nFailed to generate PCB PDF. No path found.\n')
        except Exception as e:
            self.print_output('\nAn error occurred during PCB PDF generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        try:
            gerber_and_drill_file_path = self.generate_gerber_and_drill_file()
            if gerber_and_drill_file_path:
                self.upload_gerber_and_drill_files(gerber_and_drill_file_path)
            else:
                self.print_output('\nFailed to generate Gerber and drill files. No path found.\n')
        except Exception as e:
            self.print_output('\nAn error occurred during Gerber and drill file generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        try:
            schematic_file_path = self.generate_schematic_pdf()
            if schematic_file_path:
                self.upload_schematic_pdf(schematic_file_path)
            else:
                self.print_output('\nFailed to generate schematic PDF. No path found.\n')
        except Exception as e:
            self.print_output('\nAn error occurred during schematic PDF generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        try:
            bom_path = self.generate_bom_csv()
            if bom_path:
                self.upload_bom_csv(bom_path)
            else:
                self.print_output('\nFailed to generate BOM CSV. No path found.\n')
        except Exception as e:
            self.print_output('\nAn error occurred during BOM CSV generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        try:
            zipped_position_files = self.generate_position_file()
            if zipped_position_files:
                self.upload_position_file(zipped_position_files)
            else:
                self.print_output('\nFailed to generate position file. No path found.\n')
        except Exception as e:
            self.print_output('\nAn error occurred during position file generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        self.print_output('\n\n\nUpload completed! Please check the output for any errors.\n\n\n')

        # Currently not used, waiting for KiCad to add support for 3D model export jpg/png
        # svg_file_path = self.generate_svg_thumbnail()
        # if svg_file_path:
        #     self.upload_svg_thumbnail(svg_file_path)
        # else:
        #     self.print_output('\nFailed to generate SVG thumbnail. No path found.\n')
       
    def generate_position_file(self):
        if not self.pcb_file:
            self.print_output('\nPlease open a PCB file first.\n')
            return

        self.print_output('\nGenerating position file...\n')
        wx.Yield()

        try:
            if not self.temp_file_path:
                self.generate_temp_file_folder()

            output_pos_front = os.path.join(self.temp_file_path, 'position_front.pos')
            output_pos_back = os.path.join(self.temp_file_path, 'position_back.pos')

            command_front = [
                self.kicad_cli, 'pcb', 'export', 'pos',
                '--output', output_pos_front,
                '--side', 'front',  # Front side components
                '--use-drill-file-origin',
                '--exclude-dnp',  # Exclude Do Not Populate components
                '--smd-only',  # Only include SMD components
                '--units', 'mm',
                # Default format is ascii
                self.pcb_file
            ]

            command_back = [
                self.kicad_cli, 'pcb', 'export', 'pos',
                '--output', output_pos_back,
                '--side', 'back',  # Back side components
                '--use-drill-file-origin',
                '--exclude-dnp',  # Exclude Do Not Populate components
                '--smd-only',  # Only include SMD components
                '--units', 'mm',
                # Default format is ascii
                self.pcb_file
            ]

            result = subprocess.run(
                command_front,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors='replace'
            )

            result = subprocess.run(
                command_back,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors='replace'
            )

            zip_file_name = os.path.join(self.temp_file_path, 'position_files.zip')
            with zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(output_pos_front, os.path.basename(output_pos_front))
                zipf.write(output_pos_back, os.path.basename(output_pos_back))

            os.remove(output_pos_front)
            os.remove(output_pos_back)
            
            self.print_output('\nPosition files generated and zipped successfully.\n')
            self.print_output(f'\nZIP file saved to: {zip_file_name}\n')

            return zip_file_name
        except subprocess.CalledProcessError as e:
            self.print_output('\nPosition file generation failed.\n')
            self.print_output(f"\nError output:\n{str(e.stderr)}\n")
            return None
        except Exception as e:
            self.print_output('\nAn unexpected error occurred during position file generation.\n')
            self.print_output(f"\nError: {str(e)}\n")
            self.print_output(f"\nTraceback:\n{traceback.format_exc()}\n")
            return None


    def upload_position_file(self, position_file_path):
        if not self.pcba_pk:
            self.print_output('PCBA item ID is not available.\n')
            return
        
        display_name = f"{self.pcba_number}{self.revision}_position"
        file_type = 'position'
        gerber_files = False  

        self.upload_file_to_pcba(position_file_path, display_name, file_type, gerber_files)


    def generate_schematic_pdf(self):
        if not self.schematic_file:
            self.print_output('\n\nSchematic file not specified.\n\n')
            return None

        self.print_output('\nGenerating schematic PDF...\n')
        wx.Yield()  # Update GUI

        try:
            if not self.temp_file_path:
                self.generate_temp_file_folder()

            output_pdf = os.path.join(self.temp_file_path, 'schematic.pdf')
            self.print_output(f"\nOutput PDF: {output_pdf}\n")
            self.print_output(f"\nSchematic file: {self.pcb_file}\n")

            command = [
                self.kicad_cli, 'sch', 'export', 'pdf',
                '--output', output_pdf,
                '--drawing-sheet', self.drawing_sheet_path,
                '--theme', self.theme_path,
                self.schematic_file
            ]

            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors='replace'  
            )

            self.print_output('\nSchematic PDF generated successfully.\n')
            return output_pdf
        except subprocess.CalledProcessError as e:
            self.print_output('\nSchematic PDF generation failed.\n')
            self.print_output('\n' + str(e.stderr)+ '\n')
            return None
        except Exception as e:
            self.print_output('\nAn unexpected error occurred during schematic PDF generation.')
            self.print_output(f"\nError: {str(e)}")
            self.print_output(f"\nTraceback:\n{traceback.format_exc()}")
            return None
    

    def upload_schematic_pdf(self, schematic_pdf_file_path):
        if not self.pcba_pk:
            self.print_output('\nPCBA item ID is not available.\n')
            return

        display_name = f"{self.pcba_number}{self.revision}_schematic"
        file_type = 'schematic'
        gerber_files = False

        self.upload_file_to_pcba(schematic_pdf_file_path, display_name, file_type, gerber_files)


    def generate_pcb_pdf(self):
        if not self.pcb_file:
            self.print_output('\nSchematic file not specified.\n')
            return None

        self.print_output('\nGenerating pcb PDF...\n')
        wx.Yield()  # Update GUI
        try:
            if not self.temp_file_path:
                self.generate_temp_file_folder()

            drawing_sheet_path = self.drawing_sheet_path
            theme_path = self.theme_path

            if not os.path.exists(drawing_sheet_path):
                self.print_output(f'\nDrawing sheet not found at {drawing_sheet_path}\n')
                return None

            if not os.path.exists(theme_path):
                self.print_output(f'\nTheme file not found at {theme_path}\n')
                return None

            # First PDF: Edge.Cuts and F.Fab
            output_pdf_front = os.path.join(self.temp_file_path, 'pcb_front.pdf')

            command_front = [
                self.kicad_cli, 'pcb', 'export', 'pdf',
                '--output', output_pdf_front,
                '--layers', 'Edge.Cuts,F.Fab',
                '--drawing-sheet', drawing_sheet_path,
                '--theme', theme_path,
                '--include-border-title', 
                self.pcb_file
            ]

            # Second PDF: Edge.Cuts and B.Fab, mirrored
            output_pdf_back = os.path.join(self.temp_file_path, 'pcb_back.pdf')

            command_back = [
                self.kicad_cli, 'pcb', 'export', 'pdf',
                '--output', output_pdf_back,
                '--layers', 'Edge.Cuts,B.Fab',
                '--drawing-sheet', drawing_sheet_path,
                '--theme', theme_path,
                '--mirror',
                '--include-border-title',
                self.pcb_file
            ]

            result_front = subprocess.run(
                command_front,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors='replace'  
            )

            result_back = subprocess.run(
                command_back,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors='replace'  
            )

            return output_pdf_front, output_pdf_back
        
        except subprocess.CalledProcessError as e:
            self.print_output('\nSVG generation failed.')
            self.print_output(f"\nError output:\n{str(e.stderr)}")
            return None
        except Exception as e:
            self.print_output('\nAn unexpected error occurred during SVG generation.')
            self.print_output(f"\nError: {str(e)}")
            self.print_output(f"\nTraceback:\n{traceback.format_exc()}")
            return None

    
    def upload_pcb_pdf(self, pcb_front_pdf_file_path, pcb_back_pdf_file_path):
        if not self.pcba_pk:
            self.print_output('\nPCBA item ID is not available.\n')
            return
        
        display_name_front = f"{self.pcba_number}{self.revision}_pcb_front"
        file_type_front = 'pcb_front'
        gerber_files = False  

        self.upload_file_to_pcba(pcb_front_pdf_file_path, display_name_front, file_type_front, gerber_files)

        display_name_back = f"{self.pcba_number}{self.revision}_pcb_back"
        file_type_back = 'pcb_back'

        self.upload_file_to_pcba(pcb_back_pdf_file_path, display_name_back, file_type_back, gerber_files)

    

    def generate_bom_csv(self):
        if not self.schematic_file:
            self.print_output('\nPlease open a PCB file first.')
            return None
        
        self.print_output('\nGenerating BOM CSV...\n')
        wx.Yield()  # Update GUI

        try:
            if not self.temp_file_path:
                self.generate_temp_file_folder()

            output_csv = os.path.join(self.temp_file_path, 'bom.csv')
            command = [
                self.kicad_cli, 'sch', 'export', 'bom',
                "--output", output_csv, "--fields", "Reference,MPN,${QUANTITY},${DNP}",
                "--string-delimiter", "\"", 
                "--group-by", "MPN,${DNP}",
                self.schematic_file
            ]

            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors='replace'
            )

            return output_csv
        
        except subprocess.CalledProcessError as e:
            self.print_output('\nSVG generation failed.')
            self.print_output(f"\nError output:\n{str(e.stderr)}")
            return None
        except Exception as e:
            self.print_output('\nAn unexpected error occurred during BOM generation.')
            self.print_output(f"\nError: {str(e)}")
            self.print_output(f"\nTraceback:\n{traceback.format_exc()}")
            return None
    

    def upload_bom_csv(self, bom_csv_file_path):
        if not self.pcba_pk:
            self.print_output('\nPCBA item ID is not available.\n')
            return

        headers = {
            "Authorization": f"Api-Key {self.dokuly_api_key}",
        }

        self.print_output('\nUploading BOM CSV to Dokuly...\n')
        wx.Yield()

        with open(bom_csv_file_path, 'rb') as csv_file:
            files = {'file': csv_file}
            data = {'app': "pcbas", "display_name": self.pcba_number + "_bom", "item_id": self.pcba_pk}
            try:
                if "localhost" in self.dokuly_base_api_url:
                    headers['Host'] = f"{self.dokuly_tenant}.dokuly.localhost"

                response = requests.post(self.bom_upload_url, headers=headers, files=files, data=data)

                try:
                    status = response.status_code
                    self.print_output('\n' + str(status) + '\n')  
                except Exception as e:
                    self.print_output(f"Error getting status code: {e}")

                if response.status_code in [200, 201]:
                    self.print_output('\nBOM CSV uploaded successfully.\n')
                else:
                    self.print_output(f"\nFailed to upload BOM CSV. Status code: {response.status_code}\n")
                    self.print_output(f"\nResponse: {response.text}\n")
            except requests.exceptions.RequestException as e:
                self.print_output(f"\nAn error occurred during upload: {str(e)}\n")
    
        try:
            os.remove(bom_csv_file_path)
        except Exception as e:
            self.print_output(f"\nFailed to delete {bom_csv_file_path}: {e}\n")
    

    def generate_svg_thumbnail(self):
        if not self.pcb_file:
            self.print_output('\nPlease open a PCB file first.\n')
            return None

        self.print_output('\nGenerating SVG thumbnail...\n')
        wx.Yield()  # Update GUI

        try:
            if not self.temp_file_path:
                self.generate_temp_file_folder()

            output_svg = os.path.join(self.temp_file_path, 'thumbnail.svg')
            self.print_output(f"Output SVG: {output_svg}")

            command = [
                self.kicad_cli, 'pcb', 'export', 'svg', self.pcb_file,
                '--output', output_svg,
                '--layers', 'F.Cu,F.SilkS',  
                '--page-size-mode', '2',      
                '--exclude-drawing-sheet'
            ]

            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            self.print_output('\nSVG thumbnail generated successfully.')
            return output_svg

        except subprocess.CalledProcessError as e:
            self.print_output('\nSVG generation failed.')
            self.print_output(f"Error output:\n{str(e.stderr)}")
            return None
        except Exception as e:
            self.print_output('\nAn unexpected error occurred during SVG generation.')
            self.print_output(f"Error: {str(e)}")
            self.print_output(f"Traceback:\n{traceback.format_exc()}")
            return None
        
        
    def upload_svg_thumbnail(self, svg_file_path):
        if not self.pcba_pk:
            self.print_output('\nPCBA item ID is not available.\n')
            return

        headers = {
            "Authorization": f"Api-Key {self.dokuly_api_key}",
        }

        self.print_output('\nUploading SVG thumbnail to Dokuly...\n')
        wx.Yield()  # Update GUI

        with open(svg_file_path, 'rb') as svg_file:
            files = {'file': svg_file}
            data = {'app': "pcbas", "display_name": self.pcba_number + "_thumbnail", "item_id": self.pcba_pk} 
            try:
                if "localhost" in self.dokuly_base_api_url:
                    headers['Host'] = f"{self.dokuly_tenant}.dokuly.localhost"
                
                # When using both files and data we need to send it as data and not json in requests
                response = requests.post(self.thumbnail_upload_url, headers=headers, files=files, data=data)

                if response.status_code in [200, 201]:
                    self.print_output('\nSVG thumbnail uploaded successfully.\n')
                else:
                    self.print_output(f"Failed to upload SVG thumbnail. Status code: {response.status_code}\n")
                    self.print_output(f"Response: {response.text}\n")
            except requests.exceptions.RequestException as e:
                self.print_output(f"An error occurred during upload: {str(e)}\n")

        try:
            os.remove(svg_file_path)  # Remove the file after upload
        except Exception as e:
            self.print_output(f"Failed to delete {svg_file_path}: {e}\n")

    
    def fetch_pcba_item(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.dokuly_api_key}",
        }

        # The data from kiCad is PCBAXXXX where XXXX is the pcba part number
        processed_pcba_number = int(self.pcba_number.replace("PCBA", ""), 10)
        data = {
            "part_number": processed_pcba_number,
            "revision": self.revision
        }

        wx.Yield()  # Update GUI

        try:
            if "localhost" in self.dokuly_base_api_url:
                headers['Host'] = f"{self.dokuly_tenant}.dokuly.localhost"

            response = requests.put(self.fetch_pcba_url, json=data, headers=headers)

            if response.status_code == 200:
                pcba_item = response.json()
                self.pcba_pk = pcba_item['id']
                self.update_pcba_urls()  # Update URLs now that pcba_pk is known
                self.print_output(f"\nFetched PCBA item with ID: {self.pcba_pk} and P/N {pcba_item.get('part_number')}{pcba_item.get('revision')}\n")
            else:
                self.print_output(f"\nFailed to fetch PCBA item. Status code: {str(response.status_code)}. Upload will be unavailable.\n")
                self.pcba_pk = None
        except requests.exceptions.RequestException as e:
            self.print_output(f"\nAn error occurred: {str(e)}\n")
            self.pcba_pk = None
            self.print_output("\n\nCOULD NOT FETCH PCBA FROM DOKULY; Please check your connection and relaunch the plugin!\n\n")


    def generate_gerber_and_drill_file(self):
        if not self.pcb_file:
            self.print_output('\nPlease open a PCB file first.\n')
            return

        if not self.pcba_number or not self.revision:
            self.print_output('\nPCBA_NUMBER or REVISION is not set in board variables.\n')
            return

        self.print_output('\nGenerating Gerber and drill files...\n')
        wx.Yield()  # Update GUI

        try:
            output_dir = self.temp_file_path
            if not self.temp_file_path:
                self.generate_temp_file_folder()
            # Create a subdirectory for the Gerber and drill files
            project_name = os.path.splitext(os.path.basename(self.pcb_file))[0]
            gerber_dir = os.path.join(output_dir, f"{project_name}_Gerber")
            os.makedirs(gerber_dir, exist_ok=True)

            # Generate Gerber files
            subprocess.run(
                [self.kicad_cli, 'pcb', 'export', 'gerbers', self.pcb_file, '--output', gerber_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Generate Drill files
            subprocess.run(
                [self.kicad_cli, 'pcb', 'export', 'drill', self.pcb_file, '--output', gerber_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            zip_file_name = os.path.join(output_dir, f"{project_name}_Gerber.zip")
            with zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(gerber_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, gerber_dir)
                        zipf.write(file_path, arcname)
            self.print_output('\nGerber and drill files generated and zipped successfully.\n')
            self.print_output(f'\nZIP file saved to: {zip_file_name}\n')

            shutil.rmtree(gerber_dir)
            return zip_file_name

        except subprocess.CalledProcessError as e:
            self.print_output('\nFile generation failed.\n')
            self.print_output('\n' + str(e.stderr) + '\n')
            return None
        except Exception as e:
            self.print_output('\nAn error occurred during zipping.\n')
            self.print_output('\n' + str(e) + '\n')
            return None


    def upload_gerber_and_drill_files(self, gerber_and_drill_file_path):
        if not self.pcba_pk:
            self.print_output('PCBA item ID is not available.\n')
            return
        
        display_name = f"{self.pcba_number}{self.revision}_gerber"
        file_type = 'gerber'
        gerber_files = True  

        self.upload_file_to_pcba(gerber_and_drill_file_path, display_name, file_type, gerber_files)


    def upload_file_to_pcba(self, file_path, display_name, file_type, gerber_files):
        headers = {
            "Authorization": f"Api-Key {self.dokuly_api_key}",
        }

        self.print_output(f'Uploading {display_name} to Dokuly...\n')
        wx.Yield()  # Update GUI

        with open(file_path, 'rb') as file_to_upload:
            files = {'file': file_to_upload}
            data = {'app': "pcbas", "display_name": display_name, 
                    "item_id": self.pcba_pk, "gerber": gerber_files, "replace_files": self.replace_files}

            self.print_output(f"\nGerber files: {gerber_files} for file {display_name}\n")    
        
            try:
                if "localhost" in self.dokuly_base_api_url:
                    headers['Host'] = f"{self.dokuly_tenant}.dokuly.localhost"

                response = requests.post(self.file_upload_pcba_url, headers=headers, files=files, data=data, timeout=60)

                try:
                    self.print_output(str(response.status_code))  
                except Exception as e:
                    self.print_output(f"Error getting status code: {str(e)}")

                if response.status_code in [200, 201]:
                    self.print_output(f'{display_name} uploaded successfully.\n')
                else:
                    self.print_output(f"Failed to upload {display_name}. Status code: {str(response.status_code)}\n")
                    self.print_output(f"Response: {response.text}\n")
            except requests.exceptions.RequestException as e:
                self.print_output(f"An error occurred during upload: {str(e)}\n")
        try:
            os.remove(file_path)  # Remove the file after upload
        except Exception as e:
            self.print_output(f"Failed to delete {file_path}: {e}\n")


    def get_dokuly_base_api_url(self):
        if ("localhost" or "127.0.0.1") in self.dokuly_url:
            return f"http://{self.dokuly_url}"
        return f"{self.url_protocol}://{self.dokuly_tenant}.{self.dokuly_url}"
    

    def load_env_file(self, env_path=".env"):
        """
        Load environment variables from a .env file.
        
        Args:
            env_path (str): Path to the .env file. Defaults to ".env" in the current directory.
        """
        plugin_dir = os.path.dirname(__file__)
        full_env_path = os.path.join(plugin_dir, env_path)
        if not os.path.exists(full_env_path):
            self.print_output(f".env file not found at {full_env_path}")
            self.print_output(f"Current working directory: {os.getcwd()}")
            return
    
        with open(full_env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, value = line.split('=', 1)

                # Load environment variables
                if key == 'DOKULY_API_KEY':
                    self.dokuly_api_key = value
                elif key == 'DOKULY_TENANT':
                    self.dokuly_tenant = value
                elif key == 'DOKULY_URL':
                    self.dokuly_url = value
                elif key == 'THEME_PATH':
                    self.theme_path = value
                elif key == 'DRAWING_SHEET_PATH':
                    self.drawing_sheet_path = value
                elif key == 'REPLACE_FILES':
                    if value.lower() == 'true':
                        self.replace_files = True



# KiCad Plugin Class
def register_plugin():
    class KiCadToDokulyPlugin(pcbnew.ActionPlugin):
        def defaults(self):
            self.name = "KiCad to dokuly"
            self.category = "Utility"
            self.description = "Generate Gerber/Drill/Schematic files, and upload them together with your BOM to dokuly."
            self.show_toolbar_button = True  # Display the plugin in the toolbar
            self.icon_file_name = self.get_icon_path()  # Provide the path to the icon file

        def get_icon_path(self):
            # Get the directory of the current script
            plugin_dir = os.path.dirname(__file__)
            icon_path = os.path.join(plugin_dir, 'kicaduploadSmall.png')
            return icon_path

        def Run(self):
            # Attempt to get KiCad's main frame
            try:
                pcbnew_frame = self.get_pcbnew_frame()
            except Exception as e:
                pcbnew_frame = None  # Fallback to None if unable to get the frame

            # Create and show the GUI
            frame = KiCadTool(pcbnew_frame, self.name)

        def get_pcbnew_frame(self):
            # Try to get the main frame using different methods
            # Method 1: pcbnew.GetMainFrame()
            if hasattr(pcbnew, 'GetMainFrame'):
                return pcbnew.GetMainFrame()

            # Method 2: pcbnew.GetFrame()
            if hasattr(pcbnew, 'GetFrame'):
                return pcbnew.GetFrame()

            # Method 3: wx.GetTopLevelWindows()
            for window in wx.GetTopLevelWindows():
                if 'Pcbnew' in window.GetTitle():
                    return window

            # Method 4: wx.GetApp().GetTopWindow()
            return wx.GetApp().GetTopWindow()

    # Register the plugin
    KiCadToDokulyPlugin().register()

register_plugin()