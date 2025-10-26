import os
import subprocess
import zipfile
import shutil
import json
import requests
import platform
from pathlib import Path
from datetime import datetime
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
        self.overwrite_files = True
        self.replace_files = True  # Add missing variable

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
        """Enhanced kicad-cli detection with better error handling"""
        possible_paths = []
        
        if platform.system() == 'Windows':
            possible_paths.extend([
                r'C:\Program Files\KiCad\9.0\bin\kicad-cli.exe',
                r'C:\Program Files\KiCad\8.0\bin\kicad-cli.exe',
                r'C:\Program Files\KiCad\7.0\bin\kicad-cli.exe',
            ])
        elif platform.system() == 'Darwin':  # macOS
            possible_paths.extend([
                '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
                '/usr/local/bin/kicad-cli',
            ])
        else:  # Linux
            possible_paths.extend([
                '/usr/bin/kicad-cli',
                '/usr/local/bin/kicad-cli',
            ])
        
        # Check installed paths
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Test if kicad-cli is in PATH
        try:
            result = subprocess.run(['kicad-cli', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return 'kicad-cli'
        except:
            pass
        
        return None  # Return None if not found

    def validate_kicad_cli(self):
        """Validate that kicad-cli is working"""
        if not self.kicad_cli:
            return False, "kicad-cli not found"
        
        try:
            result = subprocess.run([self.kicad_cli, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return True, f"kicad-cli version: {result.stdout.strip()}"
            else:
                return False, f"kicad-cli error: {result.stderr}"
        except Exception as e:
            return False, f"kicad-cli test failed: {str(e)}"

    def initUI(self):
        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # Configuration status indicator
        config_status = wx.BoxSizer(wx.HORIZONTAL)
        self.config_status_label = wx.StaticText(panel, label='Configuration: ')
        self.config_status_indicator = wx.StaticText(panel, label='Checking...')
        config_status.Add(self.config_status_label, flag=wx.RIGHT, border=5)
        config_status.Add(self.config_status_indicator, proportion=1)
        vbox.Add(config_status, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Configuration and test buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        self.config_button = wx.Button(panel, label='Configure Plugin')
        self.config_button.Bind(wx.EVT_BUTTON, self.show_config_wizard)
        button_box.Add(self.config_button, flag=wx.EXPAND | wx.RIGHT, border=5)
        
        self.test_button = wx.Button(panel, label='Test Components')
        self.test_button.Bind(wx.EVT_BUTTON, self.test_plugin_components)
        button_box.Add(self.test_button, flag=wx.EXPAND)
        
        vbox.Add(button_box, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Label to show selected PCB file
        self.label = wx.StaticText(panel, label='No PCB file selected.')
        vbox.Add(self.label, flag=wx.EXPAND | wx.LEFT |
                 wx.RIGHT | wx.TOP, border=10)

        # Display PCBA_NUMBER and REVISION
        name_box = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(panel, label='PCBA_NUMBER:')
        self.pcba_number_value = wx.StaticText(panel, label='')
        name_box.Add(name_label, flag=wx.RIGHT, border=8)
        name_box.Add(self.pcba_number_value, proportion=1)
        vbox.Add(name_box, flag=wx.EXPAND | wx.LEFT |
                 wx.RIGHT | wx.TOP, border=10)

        revision_box = wx.BoxSizer(wx.HORIZONTAL)
        revision_label = wx.StaticText(panel, label='REVISION:')
        self.revision_value = wx.StaticText(panel, label='')
        revision_box.Add(revision_label, flag=wx.RIGHT, border=8)
        revision_box.Add(self.revision_value, proportion=1)
        vbox.Add(revision_box, flag=wx.EXPAND |
                 wx.LEFT | wx.RIGHT | wx.TOP, border=10)

       # Button to Sync PCBA to dokuly
        sync_button = wx.Button(panel, label='Push PCBA to Dokuly (All Files)')
        sync_button.Bind(wx.EVT_BUTTON, self.push_pcba_to_dokuly)
        vbox.Add(sync_button, flag=wx.EXPAND |
                 wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Text area to display output
        self.output_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        vbox.Add(self.output_text, proportion=1,
                 flag=wx.EXPAND | wx.ALL, border=10)

        panel.SetSizer(vbox)

        self.load_env_file()

        self.dokuly_base_api_url = self.get_dokuly_base_api_url()

        # Check configuration status
        self.check_configuration_status()

        # Get the currently open PCB file
        self.get_current_pcb_file()

        # Get PCBA_NUMBER and REVISION from board variables
        self.populate_board_variables()

        self.update_pcba_urls()

        # Fetch PCBA item from dokuly (only if properly configured)
        if self.pcba_number and self.revision and self.dokuly_api_key:
            self.fetch_pcba_item()
        else:
            self.print_output("\n🎯 Welcome to KiCad to Dokuly Plugin!\n")
            self.print_output("To get started:\n")
            self.print_output("1. Click 'Configure Plugin' to set up your Dokuly credentials\n")
            self.print_output("2. Set PCBA_NUMBER and PCBA_REVISION in your board variables\n")
            self.print_output("3. Click 'Push PCBA to Dokuly' to upload your files\n\n")

        self.generate_temp_file_folder()

    def print_output(self, message):
        self.output_text.AppendText(message)

    def debug_log(self, message, level="INFO"):
        """Add debug logging for troubleshooting"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        
        if level == "ERROR":
            self.print_output(f"❌ {log_message}\n")
        elif level == "WARNING":
            self.print_output(f"⚠️ {log_message}\n")
        else:
            self.print_output(f"ℹ️ {log_message}\n")

    def make_request(self, method, url, **kwargs):
        """Make HTTP request with proper handling"""
        headers = kwargs.get('headers', {})
        
        # Simple direct request for all environments (no tenant subdomains)
        self.debug_log(f"Making {method} request to {url}")
        return requests.request(method, url, **kwargs)

    def handle_request_error(self, response, operation_name):
        """Standardized error handling for HTTP requests"""
        if response.status_code in [200, 201]:
            self.print_output(f'{operation_name} completed successfully.\n')
            return True
        else:
            self.print_output(f"Failed to {operation_name.lower()}. Status code: {response.status_code}\n")
            self.print_output(f"Response: {response.text}\n")
            return False

    def validate_dokuly_connection(self):
        """Test if Dokuly is accessible using correct API endpoints"""
        if not self.dokuly_api_key or not self.dokuly_url:
            return False
            
        try:
            headers = {
                "Authorization": f"Api-Key {self.dokuly_api_key}",
            }
            
            # Use CORRECT API endpoints that actually exist in Dokuly
            test_endpoints = [
                f"{self.dokuly_base_api_url}/api/v1/pcbas/",           # ✅ Exists
                f"{self.dokuly_base_api_url}/api/v1/parts/",           # ✅ Exists  
                f"{self.dokuly_base_api_url}/api/v1/assemblies/",      # ✅ Exists
                f"{self.dokuly_base_api_url}/api/v1/documents/",       # ✅ Exists
                f"{self.dokuly_base_api_url}/api/v1/customers/",       # ✅ Exists
            ]
            
            for test_url in test_endpoints:
                try:
                    response = self.make_request('GET', test_url, headers=headers, timeout=5)
                    # 401/403 means Dokuly is reachable but auth failed, which is acceptable for validation
                    if response.status_code in [200, 401, 403]:
                        return True
                except:
                    continue
            
            return False
        except Exception as e:
            self.debug_log(f"Dokuly connection validation failed: {str(e)}", "WARNING")
            return False

    def validate_env_config(self):
        """Validate environment configuration values"""
        errors = []
        
        if self.dokuly_url and not self.url_protocol:
            errors.append("URL_PROTOCOL is required when DOKULY_URL is set")
        
        if self.theme_path and not os.path.exists(self.theme_path):
            errors.append(f"THEME_PATH file not found: {self.theme_path}")
        
        if self.drawing_sheet_path and not os.path.exists(self.drawing_sheet_path):
            errors.append(f"DRAWING_SHEET_PATH file not found: {self.drawing_sheet_path}")
        
        return errors

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
                self.label.SetLabel(
                    f'Selected PCB file: {os.path.basename(self.pcb_file)}')

                # try to find the schematic file
                project_dir = os.path.dirname(self.pcb_file)
                project_name = os.path.splitext(
                    os.path.basename(self.pcb_file))[0]
                self.schematic_file = os.path.join(
                    project_dir, f"{project_name}.kicad_sch")
                if os.path.exists(self.schematic_file):
                    self.print_output(
                        f"Schematic file found: {self.schematic_file}\n")
                else:
                    self.print_output(
                        f"Schematic file not found: {self.schematic_file}\n")
                    self.schematic_file = ''  # reset if not found
            else:
                self.label.SetLabel('No PCB file selected.')
        else:
            self.label.SetLabel('No PCB file selected.')

    def populate_board_variables(self):
        """Improved board variable access with debugging"""
        board = pcbnew.GetBoard()
        if board is not None:
            try:
                self.debug_log("Attempting to fetch board variables...", "INFO")
                
                # Method 1: Try GetTextVars (KiCad 6+)
                if hasattr(board, 'GetTextVars'):
                    self.debug_log("Using GetTextVars method", "INFO")
                    variables = board.GetTextVars()
                    self.pcba_number = variables.get('PCBA_NUMBER', '')
                    self.revision = variables.get('PCBA_REVISION', '')
                    self.debug_log(f"GetTextVars - PCBA_NUMBER: '{self.pcba_number}', PCBA_REVISION: '{self.revision}'", "INFO")
                else:
                    # Method 2: Try GetProperties (handle different return types)
                    self.debug_log("Using GetProperties method", "INFO")
                    variables = board.GetProperties()
                    self.debug_log(f"GetProperties returned: {type(variables)}", "INFO")
                    
                    if hasattr(variables, 'get'):
                        # It's a dict-like object
                        self.pcba_number = variables.get('PCBA_NUMBER', '')
                        self.revision = variables.get('PCBA_REVISION', '')
                        self.debug_log(f"Dict-like access - PCBA_NUMBER: '{self.pcba_number}', PCBA_REVISION: '{self.revision}'", "INFO")
                    else:
                        # It's a MAP_STRING_STRING object, access with try/except
                        self.debug_log("Using MAP_STRING_STRING access method", "INFO")
                        self.debug_log(f"Available variables: {list(variables.keys()) if hasattr(variables, 'keys') else 'No keys method'}", "INFO")
                        
                        # Try different access methods for MAP_STRING_STRING
                        try:
                            # Method 1: Direct access
                            self.pcba_number = variables['PCBA_NUMBER'] if 'PCBA_NUMBER' in variables else ''
                        except:
                            try:
                                # Method 2: Using get method
                                self.pcba_number = variables.get('PCBA_NUMBER') or ''
                            except:
                                # Method 3: Iterate through items
                                self.pcba_number = ''
                                for key, value in variables:
                                    if key == 'PCBA_NUMBER':
                                        self.pcba_number = value
                                        break
                        
                        try:
                            # Method 1: Direct access
                            self.revision = variables['PCBA_REVISION'] if 'PCBA_REVISION' in variables else ''
                        except:
                            try:
                                # Method 2: Using get method
                                self.revision = variables.get('PCBA_REVISION') or ''
                            except:
                                # Method 3: Iterate through items
                                self.revision = ''
                                for key, value in variables:
                                    if key == 'PCBA_REVISION':
                                        self.revision = value
                                        break
                        
                        self.debug_log(f"MAP_STRING_STRING access - PCBA_NUMBER: '{self.pcba_number}', PCBA_REVISION: '{self.revision}'", "INFO")
                    
                # Method 3: Try GetProjectTextVars (alternative)
                if not self.pcba_number and hasattr(board, 'GetProjectTextVars'):
                    self.debug_log("Trying GetProjectTextVars as fallback", "INFO")
                    project_vars = board.GetProjectTextVars()
                    if hasattr(project_vars, 'get'):
                        self.pcba_number = project_vars.get('PCBA_NUMBER', '')
                        self.revision = project_vars.get('PCBA_REVISION', '')
                        self.debug_log(f"GetProjectTextVars - PCBA_NUMBER: '{self.pcba_number}', PCBA_REVISION: '{self.revision}'", "INFO")
                    else:
                        # Handle MAP_STRING_STRING object for project vars too
                        try:
                            if not self.pcba_number:
                                self.pcba_number = project_vars.get('PCBA_NUMBER') or ''
                        except:
                            pass
                        try:
                            if not self.revision:
                                self.revision = project_vars.get('PCBA_REVISION') or ''
                        except:
                            pass
                        self.debug_log(f"GetProjectTextVars MAP_STRING_STRING - PCBA_NUMBER: '{self.pcba_number}', PCBA_REVISION: '{self.revision}'", "INFO")
                
                # Final result
                self.debug_log(f"Final result - PCBA_NUMBER: '{self.pcba_number}', PCBA_REVISION: '{self.revision}'", "INFO")
                    
            except Exception as e:
                self.debug_log(f"Error accessing board variables: {str(e)}", "ERROR")
                self.pcba_number = ''
                self.revision = ''

            self.pcba_number_value.SetLabel(self.pcba_number)
            self.revision_value.SetLabel(self.revision)

        else:
            self.debug_log("No board loaded", "WARNING")

    def test_plugin_components(self):
        """Test individual plugin components"""
        self.debug_log("=== Plugin Component Tests ===", "INFO")
        
        # Test 1: KiCad CLI
        cli_valid, cli_msg = self.validate_kicad_cli()
        self.debug_log(f"KiCad CLI: {cli_msg}", "INFO" if cli_valid else "ERROR")
        
        # Test 2: Board access
        board = pcbnew.GetBoard()
        if board:
            self.debug_log("Board loaded successfully", "INFO")
            self.debug_log(f"Board file: {board.GetFileName()}", "INFO")
        else:
            self.debug_log("No board loaded", "WARNING")
        
        # Test 3: Configuration
        config_status = []
        if self.dokuly_api_key: config_status.append("API_KEY")
        if self.dokuly_url: config_status.append("URL")
        if self.theme_path: config_status.append("THEME")
        if self.drawing_sheet_path: config_status.append("DRAWING_SHEET")
        self.debug_log(f"Configuration: {', '.join(config_status)}", "INFO")
        
        # Test 4: API Connection
        if self.dokuly_api_key and self.dokuly_url:
            api_valid = self.validate_dokuly_connection()
            self.debug_log(f"API Connection: {'Valid' if api_valid else 'Failed'}", "INFO" if api_valid else "ERROR")

    def create_production_zip(self, event):
        """Create a production-ready ZIP file with all necessary files"""
        self.print_output("\n📦 Creating Production ZIP Package...\n")
        
        # Check if we have the required information
        if not self.pcba_number or not self.revision:
            self.print_output("❌ Missing PCBA_NUMBER or PCBA_REVISION. Please set these in your board variables.\n")
            return
        
        if not self.pcb_file:
            self.print_output("❌ No PCB file selected. Please open a PCB file in KiCad.\n")
            return
        
        try:
            # Create production directory
            production_dir = os.path.join(self.temp_file_path, 'production')
            if os.path.exists(production_dir):
                shutil.rmtree(production_dir)
            os.makedirs(production_dir)
            
            # Generate all required files
            self.print_output("🔧 Generating production files...\n")
            
            # 1. Generate Gerber files
            gerber_dir = os.path.join(production_dir, 'gerbers')
            os.makedirs(gerber_dir)
            if self.generate_gerber_files(gerber_dir):
                self.print_output("✅ Gerber files generated\n")
            else:
                self.print_output("❌ Failed to generate Gerber files\n")
                return
            
            # 2. Generate Drill files
            drill_dir = os.path.join(production_dir, 'drill')
            os.makedirs(drill_dir)
            if self.generate_drill_files(drill_dir):
                self.print_output("✅ Drill files generated\n")
            else:
                self.print_output("❌ Failed to generate drill files\n")
                return
            
            # 3. Generate Position files
            pos_dir = os.path.join(production_dir, 'position')
            os.makedirs(pos_dir)
            if self.generate_position_files(pos_dir):
                self.print_output("✅ Position files generated\n")
            else:
                self.print_output("❌ Failed to generate position files\n")
                return
            
            # 4. Generate BOM file
            bom_file = os.path.join(production_dir, 'bom.csv')
            if self.generate_bom_file(bom_file):
                self.print_output("✅ BOM file generated\n")
            else:
                self.print_output("❌ Failed to generate BOM file\n")
                return
            
            # 5. Generate PDF files
            pdf_dir = os.path.join(production_dir, 'pdfs')
            os.makedirs(pdf_dir)
            front_pdf, back_pdf = self.generate_pcb_pdf()
            if front_pdf and back_pdf:
                shutil.copy2(front_pdf, os.path.join(pdf_dir, 'pcb_front.pdf'))
                shutil.copy2(back_pdf, os.path.join(pdf_dir, 'pcb_back.pdf'))
                self.print_output("✅ PDF files generated\n")
            
            # 6. Create ZIP file
            zip_filename = f"{self.pcba_number}_{self.revision}_PRODUCTION.zip"
            zip_path = os.path.join(os.path.dirname(self.pcb_file), zip_filename)
            
            self.print_output(f"📦 Creating ZIP file: {zip_filename}\n")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(production_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, production_dir)
                        zipf.write(file_path, arcname)
            
            # Get file size
            file_size = os.path.getsize(zip_path)
            size_mb = file_size / (1024 * 1024)
            
            self.print_output(f"🎉 Production ZIP created successfully!\n")
            self.print_output(f"📁 Location: {zip_path}\n")
            self.print_output(f"📊 Size: {size_mb:.2f} MB\n")
            self.print_output(f"📋 Contents:\n")
            self.print_output(f"   • Gerber files (all layers)\n")
            self.print_output(f"   • Drill files (PTH and NPTH)\n")
            self.print_output(f"   • Position files (front and back)\n")
            self.print_output(f"   • BOM file (CSV format)\n")
            self.print_output(f"   • PDF files (front and back)\n")
            
            # Ask if user wants to open the file location
            result = wx.MessageBox(
                f"Production ZIP created successfully!\n\nFile: {zip_filename}\nSize: {size_mb:.2f} MB\n\nWould you like to open the file location?",
                "Production ZIP Created",
                wx.YES_NO | wx.ICON_INFORMATION
            )
            
            if result == wx.YES:
                # Open file location (platform-specific)
                if platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', '-R', zip_path])
                elif platform.system() == 'Windows':
                    subprocess.run(['explorer', '/select,', zip_path])
                else:  # Linux
                    subprocess.run(['xdg-open', os.path.dirname(zip_path)])
            
        except Exception as e:
            self.print_output(f"❌ Error creating production ZIP: {str(e)}\n")
            self.debug_log(f"Production ZIP creation error: {str(e)}", "ERROR")

    def generate_gerber_files(self, output_dir):
        """Generate Gerber files for all layers"""
        try:
            # Get all layers from the board
            board = pcbnew.GetBoard()
            if not board:
                return False
            
            # Common Gerber layers
            layers = [
                'F.Cu', 'B.Cu',  # Copper layers
                'F.SilkS', 'B.SilkS',  # Silkscreen
                'F.Mask', 'B.Mask',  # Solder mask
                'F.Paste', 'B.Paste',  # Solder paste
                'Edge.Cuts',  # Board outline
                'F.Fab', 'B.Fab',  # Fabrication layers
            ]
            
            for layer in layers:
                try:
                    output_file = os.path.join(output_dir, f"{layer}.gbr")
                    command = [
                        self.kicad_cli, 'pcb', 'export', 'gerbers',
                        '--output', output_file,
                        '--layers', layer,
                        self.pcb_file
                    ]
                    
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode != 0:
                        self.debug_log(f"Failed to generate {layer}: {result.stderr}", "WARNING")
                        
                except Exception as e:
                    self.debug_log(f"Error generating {layer}: {str(e)}", "WARNING")
                    continue
            
            return True
            
        except Exception as e:
            self.debug_log(f"Error in generate_gerber_files: {str(e)}", "ERROR")
            return False

    def generate_drill_files(self, output_dir):
        """Generate drill files (PTH and NPTH) using KiCad 9.0 syntax"""
        try:
            self.debug_log(f"Generating drill files in: {output_dir}", "INFO")
            
            # KiCad 9.0 uses --excellon-separate-th to generate separate PTH and NPTH files
            command = [
                self.kicad_cli, 'pcb', 'export', 'drill',
                '--output', output_dir,
                '--format', 'excellon',
                '--excellon-separate-th',
                self.pcb_file
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check if files were created (KiCad 9.0 creates files with PCB name)
            success = result.returncode == 0
            
            if success and os.path.exists(output_dir):
                files = os.listdir(output_dir)
                pth_files = [f for f in files if 'PTH' in f and f.endswith('.drl')]
                npth_files = [f for f in files if 'NPTH' in f and f.endswith('.drl')]
                
                success = len(pth_files) > 0 and len(npth_files) > 0
                
                if success:
                    self.debug_log("Drill files generated successfully", "INFO")
                else:
                    self.debug_log("Drill generation failed - missing PTH or NPTH files", "ERROR")
            else:
                self.debug_log("Drill generation failed", "ERROR")
            
            return success
            
        except Exception as e:
            self.debug_log(f"Error in generate_drill_files: {str(e)}", "ERROR")
            return False

    def generate_position_files(self, output_dir):
        """Generate position files for front and back"""
        try:
            # Generate front position file
            front_file = os.path.join(output_dir, "position_front.csv")
            command_front = [
                self.kicad_cli, 'pcb', 'export', 'pos',
                '--output', front_file,
                '--format', 'csv',
                '--side', 'front',
                self.pcb_file
            ]
            
            result_front = subprocess.run(
                command_front,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Generate back position file
            back_file = os.path.join(output_dir, "position_back.csv")
            command_back = [
                self.kicad_cli, 'pcb', 'export', 'pos',
                '--output', back_file,
                '--format', 'csv',
                '--side', 'back',
                self.pcb_file
            ]
            
            result_back = subprocess.run(
                command_back,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result_front.returncode == 0 and result_back.returncode == 0
            
        except Exception as e:
            self.debug_log(f"Error in generate_position_files: {str(e)}", "ERROR")
            return False

    def generate_bom_file(self, output_file):
        """Generate BOM file from schematic"""
        try:
            self.debug_log(f"Generating BOM file: {output_file}", "INFO")
            
            if not self.schematic_file or not os.path.exists(self.schematic_file):
                self.debug_log("Schematic file not found for BOM generation", "WARNING")
                return False
            
            # Try multiple BOM command variations for KiCad 9.0 with Dokuly-compatible format
            commands_to_try = [
                # Command 1: Custom fields for Dokuly API format
                [
                    self.kicad_cli, 'sch', 'export', 'bom',
                    '--output', output_file,
                    '--fields', 'Reference,Value,Footprint,${QUANTITY},${DNP}',
                    '--labels', 'Reference,MPN,Footprint,QUANTITY,DNP',
                    '--field-delimiter', ',',
                    '--string-delimiter', '"',
                    '--exclude-dnp',
                    self.schematic_file
                ],
                # Command 2: Alternative field mapping
                [
                    self.kicad_cli, 'sch', 'export', 'bom',
                    '--output', output_file,
                    '--fields', 'Reference,Value,${QUANTITY},${DNP}',
                    '--labels', 'Reference,MPN,QUANTITY,DNP',
                    '--field-delimiter', ',',
                    '--string-delimiter', '"',
                    self.schematic_file
                ],
                # Command 3: Basic command with default fields
                [
                    self.kicad_cli, 'sch', 'export', 'bom',
                    '--output', output_file,
                    '--field-delimiter', ',',
                    '--string-delimiter', '"',
                    self.schematic_file
                ]
            ]
            
            for i, command in enumerate(commands_to_try):
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and os.path.exists(output_file):
                    # Post-process the BOM file to ensure Dokuly-compatible format
                    if self.post_process_bom_file(output_file):
                        self.debug_log("BOM file generated successfully", "INFO")
                        return True
                    else:
                        self.debug_log("BOM file post-processing failed", "WARNING")
                        continue
                else:
                    continue
            
            self.debug_log("All BOM generation commands failed", "ERROR")
            return False
            
        except Exception as e:
            self.debug_log(f"Error in generate_bom_file: {str(e)}", "ERROR")
            return False

    def post_process_bom_file(self, bom_file_path):
        """Post-process BOM file to ensure Dokuly-compatible format"""
        try:
            
            # Read the generated BOM file
            with open(bom_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                self.debug_log("BOM file is empty", "ERROR")
                return False
            
            # Process the header and data
            processed_lines = []
            header_processed = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if not header_processed:
                    # Process header to ensure correct column names
                    header = line.split(',')
                    processed_header = []
                    
                    for col in header:
                        col = col.strip().strip('"')
                        # Map common column names to Dokuly format
                        if col.lower() in ['ref', 'reference', 'designator', 'find', 'f/n', 'find no', 'parts']:
                            processed_header.append('Reference')
                        elif col.lower() in ['value', 'part number', 'p/n', 'part no', 'pn', 'mpn']:
                            processed_header.append('MPN')
                        elif col.lower() in ['quantity', 'qty', 'amount']:
                            processed_header.append('QUANTITY')
                        elif col.lower() in ['dnp', 'dn', 'do not mount', 'dnm']:
                            processed_header.append('DNP')
                        else:
                            processed_header.append(col)
                    
                    # Ensure we have the required columns
                    required_columns = ['Reference', 'MPN', 'QUANTITY']
                    for req_col in required_columns:
                        if req_col not in processed_header:
                            processed_header.append(req_col)
                    
                    processed_lines.append(','.join(f'"{col}"' for col in processed_header))
                    header_processed = True
                    
                else:
                    # Process data rows
                    parts = line.split(',')
                    processed_parts = []
                    
                    for i, part in enumerate(parts):
                        part = part.strip().strip('"')
                        
                        # Ensure QUANTITY is a valid integer
                        if i == processed_lines[0].count(',') - 2:  # QUANTITY column (second to last)
                            try:
                                quantity = int(part) if part else 1
                                processed_parts.append(f'"{quantity}"')
                            except ValueError:
                                processed_parts.append('"1"')
                        else:
                            processed_parts.append(f'"{part}"')
                    
                    processed_lines.append(','.join(processed_parts))
            
            # Write the processed BOM file
            with open(bom_file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(processed_lines))
            
            self.debug_log("BOM file post-processed successfully", "INFO")
            return True
            
        except Exception as e:
            self.debug_log(f"Error post-processing BOM file: {str(e)}", "ERROR")
            return False

    def get_step_version_info(self):
        """Generate version information for STEP file metadata"""
        try:
            from datetime import datetime
            
            # Get current timestamp in yymmddhhmm format
            timestamp = datetime.now().strftime("%y%m%d%H%M")
            
            # Short format version info
            version_info = f"{self.pcba_number}_{self.revision}_{timestamp}"
            
            return version_info
            
        except Exception as e:
            self.debug_log(f"Error generating version info: {str(e)}", "ERROR")
            return f"{self.pcba_number}_{self.revision}_{datetime.now().strftime('%y%m%d%H%M')}"

    def add_version_metadata_to_step(self, step_file_path):
        """Add version metadata to STEP file for mechanical integration tracking"""
        try:
            if not os.path.exists(step_file_path):
                return False
                
            # Read the STEP file
            with open(step_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Add version information as a comment in the STEP file
            version_info = self.get_step_version_info()
            version_comment = f"\n/* VERSION_INFO: {version_info} */\n"
            
            # Insert version comment after the header
            if "ISO-10303-21" in content:
                # Find the end of the header section
                header_end = content.find("ENDSEC;")
                if header_end != -1:
                    # Insert version comment after header
                    new_content = content[:header_end + 7] + version_comment + content[header_end + 7:]
                    
                    # Write back to file
                    with open(step_file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    self.debug_log("Added version metadata to STEP file", "INFO")
                    return True
            
            self.debug_log("Could not add version metadata - STEP file format not recognized", "WARNING")
            return False
            
        except Exception as e:
            self.debug_log(f"Error adding version metadata: {str(e)}", "ERROR")
            return False

    def generate_step_file(self, output_file):
        """Generate STEP file for 3D visualization and mechanical integration"""
        try:
            self.debug_log(f"Generating STEP file: {output_file}", "INFO")
            
            # Try different command variations for different KiCad versions
            commands_to_try = [
                # KiCad 9.0+ with all options and version info
                [
                    self.kicad_cli, 'pcb', 'export', 'step',
                    '--output', output_file,
                    '--subst-models',
                    '--min-distance', '0.1',
                    '--max-distance', '2.0',
                    '--define-var', f'STEP_VERSION={self.get_step_version_info()}',
                    self.pcb_file
                ],
                # KiCad 9.0+ simplified with version info
                [
                    self.kicad_cli, 'pcb', 'export', 'step',
                    '--output', output_file,
                    '--subst-models',
                    '--define-var', f'STEP_VERSION={self.get_step_version_info()}',
                    self.pcb_file
                ],
                # KiCad 9.0+ basic with version info
                [
                    self.kicad_cli, 'pcb', 'export', 'step',
                    '--output', output_file,
                    '--define-var', f'STEP_VERSION={self.get_step_version_info()}',
                    self.pcb_file
                ],
                # KiCad 9.0+ basic without version info (fallback)
                [
                    self.kicad_cli, 'pcb', 'export', 'step',
                    '--output', output_file,
                    self.pcb_file
                ],
                # Alternative syntax
                [
                    self.kicad_cli, 'pcb', 'export', 'step',
                    output_file,
                    self.pcb_file
                ]
            ]
            
            for i, command in enumerate(commands_to_try):
                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=120  # STEP generation can take longer
                    )
                    
                    # Check if file was actually created and has content (regardless of return code)
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        # Add version metadata to the STEP file
                        self.add_version_metadata_to_step(output_file)
                        self.debug_log("STEP file generated successfully", "INFO")
                        return True
                    else:
                        continue
                        
                except Exception as e:
                    self.debug_log(f"STEP generation command failed: {str(e)}", "WARNING")
                    continue
            
            # If we get here, all commands failed
            self.debug_log("All STEP generation commands failed", "ERROR")
            return False
                
        except Exception as e:
            self.debug_log(f"Error in generate_step_file: {str(e)}", "ERROR")
            return False

    def generate_step_file_for_upload(self):
        """Generate STEP file for upload to Dokuly"""
        try:
            # Include datetime in filename for version tracking
            from datetime import datetime
            timestamp = datetime.now().strftime("%y%m%d%H%M")
            step_filename = f"{self.pcba_number}_{self.revision}_{timestamp}.step"
            step_path = os.path.join(self.temp_file_path, step_filename)
            
            if self.generate_step_file(step_path):
                return step_path
            else:
                return None
                
        except Exception as e:
            self.debug_log(f"Error generating STEP file for upload: {str(e)}", "ERROR")
            return None

    def upload_step_file(self, step_file_path):
        """Upload STEP file to Dokuly"""
        try:
            self.print_output('\nUploading STEP file to Dokuly...\n')
            
            with open(step_file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(step_file_path), f, 'application/step'),
                    'display_name': (None, os.path.basename(step_file_path))
                }
                headers = {
                    "Authorization": f"Api-Key {self.dokuly_api_key}",
                }
                
                response = self.make_request('POST', self.file_upload_pcba_url, 
                                           files=files, headers=headers, timeout=60)
                
                if response.status_code in [200, 201]:
                    self.print_output('✅ STEP file uploaded successfully.\n')
                    return True
                else:
                    self.print_output(f'❌ Failed to upload STEP file. Status code: {response.status_code}\n')
                    self.print_output(f'Response: {response.text}\n')
                    return False
                    
        except Exception as e:
            self.print_output(f'❌ Error uploading STEP file: {str(e)}\n')
            self.debug_log(f"Error uploading STEP file: {str(e)}", "ERROR")
            return False

    def generate_production_zip_for_upload(self):
        """Generate production ZIP for upload to Dokuly"""
        try:
            self.debug_log("Starting production ZIP generation for upload", "INFO")
            
            # Create production directory
            production_dir = os.path.join(self.temp_file_path, 'production_upload')
            if os.path.exists(production_dir):
                shutil.rmtree(production_dir)
            os.makedirs(production_dir)
            
            # Generate all required files (same as create_production_zip but without ZIP creation)
            # 1. Generate Gerber files
            gerber_dir = os.path.join(production_dir, 'gerbers')
            os.makedirs(gerber_dir)
            if not self.generate_gerber_files(gerber_dir):
                self.debug_log("Failed to generate Gerber files", "ERROR")
                return None
            
            # 2. Generate Drill files
            drill_dir = os.path.join(production_dir, 'drill')
            os.makedirs(drill_dir)
            if not self.generate_drill_files(drill_dir):
                self.debug_log("Failed to generate drill files", "ERROR")
                return None
            
            # 3. Generate Position files
            pos_dir = os.path.join(production_dir, 'position')
            os.makedirs(pos_dir)
            if not self.generate_position_files(pos_dir):
                self.debug_log("Failed to generate position files", "ERROR")
                return None
            
            # 4. Generate BOM file
            bom_file = os.path.join(production_dir, 'bom.csv')
            if not self.generate_bom_file(bom_file):
                self.debug_log("Failed to generate BOM file", "ERROR")
                return None
            
            # 5. Generate PDF files
            pdf_dir = os.path.join(production_dir, 'pdfs')
            os.makedirs(pdf_dir)
            front_pdf, back_pdf = self.generate_pcb_pdf()
            if front_pdf and back_pdf:
                shutil.copy2(front_pdf, os.path.join(pdf_dir, 'pcb_front.pdf'))
                shutil.copy2(back_pdf, os.path.join(pdf_dir, 'pcb_back.pdf'))
            
            # Create ZIP file
            zip_filename = f"{self.pcba_number}_{self.revision}_PRODUCTION.zip"
            zip_path = os.path.join(self.temp_file_path, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(production_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, production_dir)
                        zipf.write(file_path, arcname)
            
            # Verify ZIP was created
            if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
                self.debug_log("Production ZIP created successfully", "INFO")
                return zip_path
            else:
                self.debug_log("Production ZIP was not created or is empty", "ERROR")
                return None
            
        except Exception as e:
            self.debug_log(f"Error generating production ZIP for upload: {str(e)}", "ERROR")
            return None

    def upload_production_zip(self, zip_file_path):
        """Upload production ZIP to Dokuly"""
        try:
            self.print_output('\nUploading Production ZIP to Dokuly...\n')
            
            with open(zip_file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(zip_file_path), f, 'application/zip'),
                    'display_name': (None, os.path.basename(zip_file_path))
                }
                headers = {
                    "Authorization": f"Api-Key {self.dokuly_api_key}",
                }
                
                response = self.make_request('POST', self.file_upload_pcba_url, 
                                           files=files, headers=headers, timeout=120)
                
                if response.status_code in [200, 201]:
                    self.print_output('✅ Production ZIP uploaded successfully.\n')
                    return True
                else:
                    self.print_output(f'❌ Failed to upload Production ZIP. Status code: {response.status_code}\n')
                    self.print_output(f'Response: {response.text}\n')
                    return False
                    
        except Exception as e:
            self.print_output(f'❌ Error uploading Production ZIP: {str(e)}\n')
            self.debug_log(f"Error uploading Production ZIP: {str(e)}", "ERROR")
            return False

    def generate_step_file_only(self, event):
        """Generate only a STEP file for 3D visualization"""
        self.print_output("\n🎯 Generating STEP File...\n")
        
        # Check if we have the required information
        if not self.pcba_number or not self.revision:
            self.print_output("❌ Missing PCBA_NUMBER or PCBA_REVISION. Please set these in your board variables.\n")
            return
        
        if not self.pcb_file:
            self.print_output("❌ No PCB file selected. Please open a PCB file in KiCad.\n")
            return
        
        try:
            # Generate STEP file in the same directory as PCB
            # Include datetime in filename for version tracking
            from datetime import datetime
            timestamp = datetime.now().strftime("%y%m%d%H%M")
            step_filename = f"{self.pcba_number}_{self.revision}_{timestamp}.step"
            step_path = os.path.join(os.path.dirname(self.pcb_file), step_filename)
            
            self.print_output(f"🔧 Generating STEP file: {step_filename}\n")
            
            if self.generate_step_file(step_path):
                # Get file size
                file_size = os.path.getsize(step_path)
                size_mb = file_size / (1024 * 1024)
                
                self.print_output(f"🎉 STEP file generated successfully!\n")
                self.print_output(f"📁 Location: {step_path}\n")
                self.print_output(f"📊 Size: {size_mb:.2f} MB\n")
                self.print_output(f"💡 Use this file for:\n")
                self.print_output(f"   • 3D visualization in CAD software\n")
                self.print_output(f"   • Mechanical integration and enclosure design\n")
                self.print_output(f"   • Assembly planning and verification\n")
                
                # Ask if user wants to open the file location
                result = wx.MessageBox(
                    f"STEP file generated successfully!\n\nFile: {step_filename}\nSize: {size_mb:.2f} MB\n\nWould you like to open the file location?",
                    "STEP File Generated",
                    wx.YES_NO | wx.ICON_INFORMATION
                )
                
                if result == wx.YES:
                    # Open file location (platform-specific)
                    if platform.system() == 'Darwin':  # macOS
                        subprocess.run(['open', '-R', step_path])
                    elif platform.system() == 'Windows':
                        subprocess.run(['explorer', '/select,', step_path])
                    else:  # Linux
                        subprocess.run(['xdg-open', os.path.dirname(step_path)])
            else:
                self.print_output("❌ Failed to generate STEP file. Check the debug output for details.\n")
                
        except Exception as e:
            self.print_output(f"❌ Error generating STEP file: {str(e)}\n")
            self.debug_log(f"STEP file generation error: {str(e)}", "ERROR")

    def push_pcba_to_dokuly(self, event):
        # Generate timestamp for version tracking (used throughout the method)
        from datetime import datetime
        timestamp = datetime.now().strftime("%y%m%d%H%M")
        
        # Check configuration status
        missing_configs = []
        if not self.pcba_number:
            missing_configs.append("PCBA_NUMBER (set in board variables)")
        if not self.revision:
            missing_configs.append("PCBA_REVISION (set in board variables)")
        if not self.dokuly_api_key:
            missing_configs.append("DOKULY_API_KEY (configure in plugin settings)")
        if not self.dokuly_url:
            missing_configs.append("DOKULY_URL (configure in plugin settings)")
        if not self.theme_path or not os.path.exists(self.theme_path):
            missing_configs.append("THEME_PATH (configure in plugin settings)")
        if not self.drawing_sheet_path or not os.path.exists(self.drawing_sheet_path):
            missing_configs.append("DRAWING_SHEET_PATH (configure in plugin settings)")

        if missing_configs:
            self.print_output('\n❌ Cannot upload to Dokuly. Missing configuration:\n')
            for config in missing_configs:
                self.print_output(f'   • {config}\n')
            self.print_output('\n💡 Click the "Configure Plugin" button to set up missing items.\n')
            return

        self.print_output(
            '\n\nPushing PCBA to dokuly... PLEASE WAIT UNTIL UPLOAD IS COMPLETED; DO NOT CLOSE OR RETRY.\n\n')

        try:
            pcb_front_pdf_file_path, pcb_back_pdf_file_path = self.generate_pcb_pdf()
            if pcb_front_pdf_file_path and pcb_back_pdf_file_path:
                self.upload_pcb_pdf(pcb_front_pdf_file_path,
                                    pcb_back_pdf_file_path)
            else:
                self.print_output(
                    '\nFailed to generate PCB PDF. No path found.\n')
        except Exception as e:
            self.print_output(
                '\nAn error occurred during PCB PDF generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        try:
            gerber_and_drill_file_path = self.generate_gerber_and_drill_file()
            if gerber_and_drill_file_path:
                self.upload_gerber_and_drill_files(gerber_and_drill_file_path)
            else:
                self.print_output(
                    '\nFailed to generate Gerber and drill files. No path found.\n')
        except Exception as e:
            self.print_output(
                '\nAn error occurred during Gerber and drill file generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        try:
            schematic_file_path = self.generate_schematic_pdf()
            if schematic_file_path:
                self.upload_schematic_pdf(schematic_file_path)
            else:
                self.print_output(
                    '\nFailed to generate schematic PDF. No path found.\n')
        except Exception as e:
            self.print_output(
                '\nAn error occurred during schematic PDF generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        try:
            bom_path = self.generate_bom_csv()
            if bom_path:
                self.upload_bom_csv(bom_path)
            else:
                self.print_output(
                    '\nFailed to generate BOM CSV. No path found.\n')
        except Exception as e:
            self.print_output(
                '\nAn error occurred during BOM CSV generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        try:
            zipped_position_files = self.generate_position_file()
            if zipped_position_files:
                self.upload_position_file(zipped_position_files)
            else:
                self.print_output(
                    '\nFailed to generate position file. No path found.\n')
        except Exception as e:
            self.print_output(
                '\nAn error occurred during position file generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        # Generate and upload STEP file
        try:
            step_file_path = self.generate_step_file_for_upload()
            if step_file_path:
                # Upload to Dokuly
                self.upload_step_file(step_file_path)
                # Also save locally
                local_step_path = os.path.join(os.path.dirname(self.pcb_file), 
                                             f"{self.pcba_number}_{self.revision}_{timestamp}.step")
                shutil.copy2(step_file_path, local_step_path)
                self.print_output(f'✅ STEP file saved locally: {os.path.basename(local_step_path)}\n')
            else:
                self.print_output(
                    '\nFailed to generate STEP file. No path found.\n')
        except Exception as e:
            self.print_output(
                '\nAn error occurred during STEP file generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        # Generate and upload Production ZIP
        try:
            production_zip_path = self.generate_production_zip_for_upload()
            if production_zip_path:
                # Upload to Dokuly
                self.upload_production_zip(production_zip_path)
                # Also save locally
                local_zip_path = os.path.join(os.path.dirname(self.pcb_file), 
                                            f"{self.pcba_number}_{self.revision}_PRODUCTION.zip")
                shutil.copy2(production_zip_path, local_zip_path)
                self.print_output(f'✅ Production ZIP saved locally: {os.path.basename(local_zip_path)}\n')
            else:
                self.print_output(
                    '\nFailed to generate Production ZIP. No path found.\n')
        except Exception as e:
            self.print_output(
                '\nAn error occurred during Production ZIP generation.\n')
            self.print_output(f"\nError: {str(e)}\n")

        self.print_output(
            '\n\n\n🎉 Upload completed! All files have been uploaded to Dokuly and saved locally.\n')
        self.print_output(
            '📁 Local files created:\n')
        self.print_output(
            f'   • {self.pcba_number}_{self.revision}_{timestamp}.step (3D model)\n')
        self.print_output(
            f'   • {self.pcba_number}_{self.revision}_PRODUCTION.zip (manufacturing files)\n')
        self.print_output(
            '\n📋 Files uploaded to Dokuly:\n')
        self.print_output(
            '   • PCB PDFs (front and back)\n')
        self.print_output(
            '   • Gerber and drill files\n')
        self.print_output(
            '   • Schematic PDF\n')
        self.print_output(
            '   • BOM CSV\n')
        self.print_output(
            '   • Position files\n')
        self.print_output(
            '   • STEP file (3D model)\n')
        self.print_output(
            '   • Production ZIP (complete manufacturing package)\n\n')

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

            output_pos_front = os.path.join(
                self.temp_file_path, 'position_front.pos')
            output_pos_back = os.path.join(
                self.temp_file_path, 'position_back.pos')

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

            zip_file_name = os.path.join(
                self.temp_file_path, 'position_files.zip')
            with zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(output_pos_front,
                           os.path.basename(output_pos_front))
                zipf.write(output_pos_back, os.path.basename(output_pos_back))

            os.remove(output_pos_front)
            os.remove(output_pos_back)

            self.print_output(
                '\nPosition files generated and zipped successfully.\n')
            self.print_output(f'\nZIP file saved to: {zip_file_name}\n')

            return zip_file_name
        except subprocess.CalledProcessError as e:
            self.print_output('\nPosition file generation failed.\n')
            self.print_output(f"\nError output:\n{str(e.stderr)}\n")
            return None
        except Exception as e:
            self.print_output(
                '\nAn unexpected error occurred during position file generation.\n')
            self.print_output(f"\nError: {str(e)}\n")
            self.print_output(f"\nTraceback:\n{traceback.format_exc()}\n")
            return None

    def upload_position_file(self, position_file_path):
        if not self.pcba_pk:
            self.print_output('PCBA item ID is not available.\n')
            return

        display_name = f"{self.pcba_number}_{self.revision}_position"
        file_type = 'position'
        gerber_files = False

        self.upload_file_to_pcba(
            position_file_path, display_name, file_type, gerber_files)

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
            self.print_output('\n' + str(e.stderr) + '\n')
            return None
        except Exception as e:
            self.print_output(
                '\nAn unexpected error occurred during schematic PDF generation.')
            self.print_output(f"\nError: {str(e)}")
            self.print_output(f"\nTraceback:\n{traceback.format_exc()}")
            return None

    def upload_schematic_pdf(self, schematic_pdf_file_path):
        if not self.pcba_pk:
            self.print_output('\nPCBA item ID is not available.\n')
            return

        display_name = f"{self.pcba_number}_{self.revision}_schematic"
        file_type = 'schematic'
        gerber_files = False

        self.upload_file_to_pcba(
            schematic_pdf_file_path, display_name, file_type, gerber_files)

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
                self.print_output(
                    f'\nDrawing sheet not found at {drawing_sheet_path}\n')
                return None

            if not os.path.exists(theme_path):
                self.print_output(f'\nTheme file not found at {theme_path}\n')
                return None

            # First PDF: Edge.Cuts and F.Fab
            output_pdf_front = os.path.join(
                self.temp_file_path, 'pcb_front.pdf')

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
            self.print_output(
                '\nAn unexpected error occurred during SVG generation.')
            self.print_output(f"\nError: {str(e)}")
            self.print_output(f"\nTraceback:\n{traceback.format_exc()}")
            return None

    def upload_pcb_pdf(self, pcb_front_pdf_file_path, pcb_back_pdf_file_path):
        if not self.pcba_pk:
            self.print_output('\nPCBA item ID is not available.\n')
            return

        display_name_front = f"{self.pcba_number}_{self.revision}_pcb_front"
        file_type_front = 'pcb_front'
        gerber_files = False

        self.upload_file_to_pcba(
            pcb_front_pdf_file_path, display_name_front, file_type_front, gerber_files)

        display_name_back = f"{self.pcba_number}_{self.revision}_pcb_back"
        file_type_back = 'pcb_back'

        self.upload_file_to_pcba(
            pcb_back_pdf_file_path, display_name_back, file_type_back, gerber_files)

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
            self.print_output(
                '\nAn unexpected error occurred during BOM generation.')
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
            data = {'app': "pcbas", "display_name": self.pcba_number +
                    "_bom", "item_id": self.pcba_pk}
            try:
                response = self.make_request(
                    'POST', self.bom_upload_url, headers=headers, files=files, data=data)

                self.handle_request_error(response, "BOM CSV upload")
            except requests.exceptions.RequestException as e:
                self.debug_log(f"Error uploading BOM CSV: {str(e)}", "ERROR")

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
            self.print_output(
                '\nAn unexpected error occurred during SVG generation.')
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
            data = {'app': "pcbas", "display_name": self.pcba_number +
                    "_thumbnail", "item_id": self.pcba_pk}
            try:
                response = self.make_request(
                    'POST', self.thumbnail_upload_url, headers=headers, files=files, data=data)

                self.handle_request_error(response, "SVG thumbnail upload")
            except requests.exceptions.RequestException as e:
                self.debug_log(f"Error uploading SVG thumbnail: {str(e)}", "ERROR")

        try:
            os.remove(svg_file_path)  # Remove the file after upload
        except Exception as e:
            self.print_output(f"Failed to delete {svg_file_path}: {e}\n")

    def fetch_pcba_item(self):
        # Validate inputs before proceeding
        if not self.pcba_number or not self.revision or not self.dokuly_api_key:
            self.print_output("\n❌ Cannot fetch PCBA: Missing required configuration (PCBA_NUMBER, REVISION, or API_KEY)\n")
            return
            
        if not self.pcba_number.startswith("PCBA"):
            self.print_output(f"\n❌ Invalid PCBA_NUMBER format: '{self.pcba_number}'. Should start with 'PCBA' (e.g., 'PCBA1234')\n")
            return

        try:
            # The data from kiCad is PCBAXXXX where XXXX is the pcba part number
            processed_pcba_number = int(self.pcba_number.replace("PCBA", ""), 10)
        except ValueError:
            self.print_output(f"\n❌ Invalid PCBA_NUMBER format: '{self.pcba_number}'. The part after 'PCBA' must be a number (e.g., 'PCBA1234')\n")
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.dokuly_api_key}",
        }

        data = {
            "part_number": processed_pcba_number,
            "revision": self.revision
        }

        wx.Yield()  # Update GUI

        try:
            response = self.make_request('PUT', self.fetch_pcba_url, json=data, headers=headers)

            if response.status_code == 200:
                pcba_item = response.json()
                self.pcba_pk = pcba_item['id']
                self.update_pcba_urls()  # Update URLs now that pcba_pk is known
                self.print_output(
                    f"\nFetched PCBA item with ID: {self.pcba_pk} and P/N {pcba_item.get('part_number')}{pcba_item.get('revision')}\n")
            else:
                self.print_output(
                    f"\nFailed to fetch PCBA item. Status code: {str(response.status_code)}. Upload will be unavailable.\n")
                self.pcba_pk = None
        except requests.exceptions.RequestException as e:
            self.debug_log(f"Error fetching PCBA item: {str(e)}", "ERROR")
            self.pcba_pk = None
            self.print_output(
                "\n\nCOULD NOT FETCH PCBA FROM DOKULY; Please check your connection and relaunch the plugin!\n\n")

    def generate_gerber_and_drill_file(self):
        if not self.pcb_file:
            self.print_output('\nPlease open a PCB file first.\n')
            return

        if not self.pcba_number or not self.revision:
            self.print_output(
                '\nPCBA_NUMBER or REVISION is not set in board variables.\n')
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
                [self.kicad_cli, 'pcb', 'export', 'gerbers',
                    self.pcb_file, '--output', gerber_dir, '--no-x2', '--no-protel-ext'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Generate Drill files
            subprocess.run(
                [self.kicad_cli, 'pcb', 'export', 'drill',
                    self.pcb_file, '--output', gerber_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            zip_file_name = os.path.join(
                output_dir, f"{project_name}_Gerber.zip")
            with zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(gerber_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, gerber_dir)
                        zipf.write(file_path, arcname)
            self.print_output(
                '\nGerber and drill files generated and zipped successfully.\n')
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

        display_name = f"{self.pcba_number}_{self.revision}_gerber"
        file_type = 'gerber'
        gerber_files = True

        self.upload_file_to_pcba(
            gerber_and_drill_file_path, display_name, file_type, gerber_files)

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

            self.print_output(
                f"\nGerber files: {gerber_files} for file {display_name}\n")

            try:
                response = self.make_request(
                    'POST', self.file_upload_pcba_url, headers=headers, files=files, data=data, timeout=60)

                self.handle_request_error(response, f'{display_name} upload')
            except requests.exceptions.RequestException as e:
                self.debug_log(f"Error uploading {display_name}: {str(e)}", "ERROR")
        try:
            os.remove(file_path)  # Remove the file after upload
        except Exception as e:
            self.print_output(f"Failed to delete {file_path}: {e}\n")

    def get_dokuly_base_api_url(self):
        if "localhost" in self.dokuly_url or "127.0.0.1" in self.dokuly_url:
            return f"http://{self.dokuly_url}"
        return f"{self.url_protocol}://{self.dokuly_url}"

    def load_env_file(self, env_path=".env"):
        """Load environment variables with better error handling"""
        plugin_dir = os.path.dirname(__file__)
        full_env_path = os.path.join(plugin_dir, env_path)
        
        if not os.path.exists(full_env_path):
            self.debug_log(f".env file not found at {full_env_path}", "WARNING")
            self.debug_log(f"Current working directory: {os.getcwd()}", "INFO")
            return

        try:
            with open(full_env_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if '=' not in line:
                        self.debug_log(f"Invalid line {line_num} in .env: {line}", "WARNING")
                        continue
                        
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")  # Remove quotes

                    # Load environment variables
                    if key == 'DOKULY_API_KEY':
                        self.dokuly_api_key = value
                    elif key == 'DOKULY_URL':
                        self.dokuly_url = value
                    elif key == 'THEME_PATH':
                        self.theme_path = value
                    elif key == 'DRAWING_SHEET_PATH':
                        self.drawing_sheet_path = value
                    elif key == 'REPLACE_FILES':
                        self.replace_files = value.lower() == 'true'
                    elif key == 'URL_PROTOCOL':
                        self.url_protocol = value
                        
        except Exception as e:
            self.debug_log(f"Error loading .env file: {str(e)}", "ERROR")

    def check_configuration_status(self):
        """Check if the plugin is properly configured"""
        missing_configs = []
        
        if not self.dokuly_api_key:
            missing_configs.append("DOKULY_API_KEY")
        if not self.dokuly_url:
            missing_configs.append("DOKULY_URL")
        if not self.url_protocol:
            missing_configs.append("URL_PROTOCOL")
        if not self.theme_path or not os.path.exists(self.theme_path):
            missing_configs.append("THEME_PATH (file not found)")
        if not self.drawing_sheet_path or not os.path.exists(self.drawing_sheet_path):
            missing_configs.append("DRAWING_SHEET_PATH (file not found)")
        
        # Check for configuration validation errors
        config_errors = self.validate_env_config()
        if config_errors:
            missing_configs.extend(config_errors)
        
        if missing_configs:
            self.config_status_indicator.SetLabel(f"❌ Missing: {', '.join(missing_configs[:3])}{'...' if len(missing_configs) > 3 else ''}")
            self.config_status_indicator.SetForegroundColour(wx.Colour(255, 0, 0))  # Red
        else:
            # Test Dokuly connection if all configs are present
            if self.validate_dokuly_connection():
                self.config_status_indicator.SetLabel("✅ Configured & Connected")
                self.config_status_indicator.SetForegroundColour(wx.Colour(0, 128, 0))  # Green
            else:
                self.config_status_indicator.SetLabel("⚠️ Config OK, but Dokuly unreachable")
                self.config_status_indicator.SetForegroundColour(wx.Colour(255, 165, 0))  # Orange

    def show_config_wizard(self, event):
        """Show configuration wizard dialog"""
        dialog = ConfigWizard(self)
        result = dialog.ShowModal()
        dialog.Destroy()
        
        # Always reload configuration after dialog closes (regardless of how it closed)
        print("DEBUG: Reloading configuration after wizard...")
        self.load_env_file()
        self.dokuly_base_api_url = self.get_dokuly_base_api_url()
        self.check_configuration_status()
        
        # Debug: Show what was loaded
        print(f"DEBUG: After reload - API Key: {self.dokuly_api_key[:10] if self.dokuly_api_key else 'None'}...")
        print(f"DEBUG: After reload - URL: {self.dokuly_url}")
        print(f"DEBUG: After reload - Protocol: {self.url_protocol}")
        
        # Try to fetch PCBA item if we now have the required configuration
        if self.pcba_number and self.revision and self.dokuly_api_key:
            self.print_output("\n✅ Configuration updated. Attempting to fetch PCBA item...\n")
            self.fetch_pcba_item()
        else:
            self.print_output("\n✅ Configuration updated. Please set PCBA_NUMBER and PCBA_REVISION in your board variables.\n")


class ConfigWizard(wx.Dialog):
    def __init__(self, parent):
        super(ConfigWizard, self).__init__(parent, title="KiCad to Dokuly Configuration", size=(500, 600))
        
        self.parent = parent
        self.env_data = {}
        
        self.init_ui()
        self.load_current_config()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Title
        title = wx.StaticText(panel, label="Configure KiCad to Dokuly Plugin")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        vbox.Add(title, flag=wx.EXPAND | wx.ALL, border=10)
        
        # API Key
        vbox.Add(wx.StaticText(panel, label="Dokuly API Key:"), flag=wx.LEFT | wx.TOP, border=10)
        self.api_key_ctrl = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        vbox.Add(self.api_key_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)
        
        # URL
        vbox.Add(wx.StaticText(panel, label="Dokuly URL (e.g., dokuly.com or localhost:8000):"), flag=wx.LEFT | wx.TOP, border=10)
        self.url_ctrl = wx.TextCtrl(panel)
        vbox.Add(self.url_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)
        
        # Protocol
        vbox.Add(wx.StaticText(panel, label="Protocol:"), flag=wx.LEFT | wx.TOP, border=10)
        self.protocol_ctrl = wx.Choice(panel, choices=["https", "http"])
        self.protocol_ctrl.SetSelection(0)  # Default to https
        vbox.Add(self.protocol_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)
        
        # Theme Path
        theme_box = wx.BoxSizer(wx.HORIZONTAL)
        theme_box.Add(wx.StaticText(panel, label="Theme File:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self.theme_path_ctrl = wx.TextCtrl(panel)
        theme_box.Add(self.theme_path_ctrl, proportion=1, flag=wx.EXPAND | wx.LEFT, border=5)
        theme_browse_btn = wx.Button(panel, label="Browse...")
        theme_browse_btn.Bind(wx.EVT_BUTTON, lambda e: self.browse_file(self.theme_path_ctrl, "JSON files (*.json)|*.json"))
        theme_box.Add(theme_browse_btn, flag=wx.LEFT, border=5)
        vbox.Add(theme_box, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        
        # Drawing Sheet Path
        sheet_box = wx.BoxSizer(wx.HORIZONTAL)
        sheet_box.Add(wx.StaticText(panel, label="Drawing Sheet:"), flag=wx.ALIGN_CENTER_VERTICAL)
        self.sheet_path_ctrl = wx.TextCtrl(panel)
        sheet_box.Add(self.sheet_path_ctrl, proportion=1, flag=wx.EXPAND | wx.LEFT, border=5)
        sheet_browse_btn = wx.Button(panel, label="Browse...")
        sheet_browse_btn.Bind(wx.EVT_BUTTON, lambda e: self.browse_file(self.sheet_path_ctrl, "KiCad worksheet files (*.kicad_wks)|*.kicad_wks"))
        sheet_box.Add(sheet_browse_btn, flag=wx.LEFT, border=5)
        vbox.Add(sheet_box, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        
        # Replace Files
        self.replace_files_cb = wx.CheckBox(panel, label="Replace existing files on upload")
        self.replace_files_cb.SetValue(True)
        vbox.Add(self.replace_files_cb, flag=wx.LEFT | wx.TOP, border=10)
        
        # Help text about board variables
        help_text = wx.StaticText(panel, label="💡 Don't forget to set PCBA_NUMBER and PCBA_REVISION in your board variables (File > Board Setup > Text Variables)")
        help_text.SetForegroundColour(wx.Colour(0, 100, 0))
        vbox.Add(help_text, flag=wx.LEFT | wx.TOP, border=10)
        
        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        test_btn = wx.Button(panel, label="Test Connection")
        test_btn.Bind(wx.EVT_BUTTON, self.test_connection)
        save_btn = wx.Button(panel, label="Save Configuration")
        save_btn.Bind(wx.EVT_BUTTON, self.save_config)
        cancel_btn = wx.Button(panel, label="Cancel")
        cancel_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        button_box.Add(test_btn, flag=wx.RIGHT, border=5)
        button_box.Add(save_btn, flag=wx.RIGHT, border=5)
        button_box.Add(cancel_btn)
        vbox.Add(button_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        panel.SetSizer(vbox)
        
    def browse_file(self, text_ctrl, wildcard):
        """Browse for a file and set the text control value"""
        with wx.FileDialog(self, "Select file", wildcard=wildcard) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                text_ctrl.SetValue(dialog.GetPath())
                
    def load_current_config(self):
        """Load current configuration values"""
        self.api_key_ctrl.SetValue(self.parent.dokuly_api_key or "")
        self.url_ctrl.SetValue(self.parent.dokuly_url or "dokuly.com")
        self.protocol_ctrl.SetStringSelection(self.parent.url_protocol or "https")
        
        # Auto-detect theme and drawing sheet if not set
        theme_path = self.parent.theme_path or self.auto_detect_theme()
        sheet_path = self.parent.drawing_sheet_path or self.auto_detect_drawing_sheet()
        
        self.theme_path_ctrl.SetValue(theme_path)
        self.sheet_path_ctrl.SetValue(sheet_path)
        self.replace_files_cb.SetValue(self.parent.overwrite_files)
        
    def auto_detect_theme(self):
        """Auto-detect common theme file locations"""
        common_paths = []
        
        if platform.system() == 'Windows':
            user_docs = os.path.expanduser("~/Documents")
            common_paths.extend([
                os.path.join(user_docs, "KiCad", "9.0", "template", "theme.json"),
                os.path.join(user_docs, "KiCad", "8.0", "template", "theme.json"),
                os.path.join(user_docs, "KiCad", "template", "theme.json"),
            ])
        elif platform.system() == 'Darwin':  # macOS
            user_docs = os.path.expanduser("~/Documents")
            common_paths.extend([
                os.path.join(user_docs, "KiCad", "9.0", "template", "theme.json"),
                os.path.join(user_docs, "KiCad", "8.0", "template", "theme.json"),
                os.path.join(user_docs, "KiCad", "template", "theme.json"),
            ])
        else:  # Linux
            user_docs = os.path.expanduser("~/Documents")
            common_paths.extend([
                os.path.join(user_docs, "KiCad", "9.0", "template", "theme.json"),
                os.path.join(user_docs, "KiCad", "8.0", "template", "theme.json"),
                os.path.join(user_docs, "KiCad", "template", "theme.json"),
            ])
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return ""
        
    def auto_detect_drawing_sheet(self):
        """Auto-detect common drawing sheet file locations"""
        common_paths = []
        
        if platform.system() == 'Windows':
            user_docs = os.path.expanduser("~/Documents")
            common_paths.extend([
                os.path.join(user_docs, "KiCad", "9.0", "template", "A4.kicad_wks"),
                os.path.join(user_docs, "KiCad", "8.0", "template", "A4.kicad_wks"),
                os.path.join(user_docs, "KiCad", "template", "A4.kicad_wks"),
            ])
        elif platform.system() == 'Darwin':  # macOS
            user_docs = os.path.expanduser("~/Documents")
            common_paths.extend([
                os.path.join(user_docs, "KiCad", "9.0", "template", "A4.kicad_wks"),
                os.path.join(user_docs, "KiCad", "8.0", "template", "A4.kicad_wks"),
                os.path.join(user_docs, "KiCad", "template", "A4.kicad_wks"),
            ])
        else:  # Linux
            user_docs = os.path.expanduser("~/Documents")
            common_paths.extend([
                os.path.join(user_docs, "KiCad", "9.0", "template", "A4.kicad_wks"),
                os.path.join(user_docs, "KiCad", "8.0", "template", "A4.kicad_wks"),
                os.path.join(user_docs, "KiCad", "template", "A4.kicad_wks"),
            ])
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return ""
        
    def test_connection(self, event):
        """Test the connection to Dokuly with current settings"""
        # Get current settings
        api_key = self.api_key_ctrl.GetValue()
        url = self.url_ctrl.GetValue()
        protocol = self.protocol_ctrl.GetStringSelection()
        
        if not all([url, protocol]):
            wx.MessageBox("Please fill in URL and protocol before testing connection.", "Incomplete Configuration", wx.OK | wx.ICON_WARNING)
            return
        
        # Build test URL
        if "localhost" in url or "127.0.0.1" in url:
            test_base_url = f"http://{url}"
        else:
            test_base_url = f"{protocol}://{url}"
        
        # First test: Basic connectivity (no auth required)
        try:
            response = requests.get(test_base_url, timeout=5)
            if response.status_code in [200, 404, 405]:  # 404/405 are OK, means server is reachable
                basic_connectivity = True
            else:
                basic_connectivity = False
        except Exception as e:
            wx.MessageBox(f"❌ Basic connectivity failed: {str(e)}", "Connection Test", wx.OK | wx.ICON_ERROR)
            return
        
        # Second test: API connectivity (with auth if provided)
        if api_key:
            test_endpoints = [
                f"{test_base_url}/api/",
                f"{test_base_url}/api/v1/",
                f"{test_base_url}/api/pcbas/",
                f"{test_base_url}/api/organizations/",
            ]
            
            headers = {"Authorization": f"Api-Key {api_key}"}
            api_success = False
            last_error = ""
            
            for test_url in test_endpoints:
                try:
                    response = requests.get(test_url, headers=headers, timeout=5)
                    if response.status_code in [200, 401, 403]:
                        api_success = True
                        break
                    else:
                        last_error = f"Status code: {response.status_code}\nResponse: {response.text[:200]}"
                except Exception as e:
                    last_error = str(e)
                    continue
            
            if api_success:
                wx.MessageBox("✅ Connection successful! Dokuly is reachable and API key is valid.", "Connection Test", wx.OK | wx.ICON_INFORMATION)
            else:
                # Try to get more info about the API structure
                api_info = ""
                try:
                    # Try to get API documentation or info
                    info_response = requests.get(f"{test_base_url}/api/", timeout=5)
                    if info_response.status_code == 200:
                        api_info = f"\nAPI Response: {info_response.text[:200]}..."
                except:
                    pass
                
                wx.MessageBox(f"⚠️ Server is reachable but API endpoints not found.\n{last_error}\n\nThis might be normal if your Dokuly installation uses different API paths.{api_info}\n\nYou can still try using the plugin - it will test the actual endpoints when uploading.", "Connection Test", wx.OK | wx.ICON_WARNING)
        else:
            wx.MessageBox("✅ Basic connectivity successful! Server is reachable.\n\nNote: Add API key to test authentication.", "Connection Test", wx.OK | wx.ICON_INFORMATION)

    def save_config(self, event):
        """Save configuration to .env file"""
        print("DEBUG: save_config method called!")
        
        plugin_dir = os.path.dirname(__file__)
        env_path = os.path.join(plugin_dir, '.env')
        
        # Debug: Show what we're trying to save
        print(f"DEBUG: Saving to {env_path}")
        print(f"DEBUG: API Key: {self.api_key_ctrl.GetValue()[:10]}...")
        print(f"DEBUG: URL: {self.url_ctrl.GetValue()}")
        print(f"DEBUG: Protocol: {self.protocol_ctrl.GetStringSelection()}")
        
        try:
            # Ensure the directory exists
            os.makedirs(plugin_dir, exist_ok=True)
            
            with open(env_path, 'w') as f:
                f.write(f"DOKULY_API_KEY={self.api_key_ctrl.GetValue()}\n")
                f.write(f"DOKULY_URL={self.url_ctrl.GetValue()}\n")
                f.write(f"URL_PROTOCOL={self.protocol_ctrl.GetStringSelection()}\n")
                f.write(f"THEME_PATH={self.theme_path_ctrl.GetValue()}\n")
                f.write(f"DRAWING_SHEET_PATH={self.sheet_path_ctrl.GetValue()}\n")
                f.write(f"REPLACE_FILES={str(self.replace_files_cb.GetValue()).lower()}\n")
            
            # Verify the file was created
            if os.path.exists(env_path):
                file_size = os.path.getsize(env_path)
                print(f"DEBUG: File created successfully, size: {file_size} bytes")
                wx.MessageBox(f"Configuration saved successfully!\n\nFile: {env_path}\nSize: {file_size} bytes", "Success", wx.OK | wx.ICON_INFORMATION)
                self.EndModal(wx.ID_OK)  # Close the dialog
            else:
                raise Exception("File was not created")
                
        except Exception as e:
            error_msg = f"Failed to save configuration: {str(e)}\n\nTried to save to: {env_path}"
            print(f"DEBUG: Save error: {error_msg}")
            wx.MessageBox(error_msg, "Error", wx.OK | wx.ICON_ERROR)
            # Don't close dialog on error - let user try again


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
