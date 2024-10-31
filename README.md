# KiCad to Dokuly Plugin

This plugin allows you to easily integrate KiCad with [dokuly](https://dokuly.com), enabling you to generate Gerber, Drill, PCB PDF, Schematic files, and upload them along with your Bill of Materials (BOM) directly to [dokuly](https://dokuly.com).

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [1. Locate the Plugin Folder](#1-locate-the-plugin-folder)
  - [2. Create or Edit the `.env` File](#2-create-or-edit-the-env-file)
    - [Sample `.env` File](#sample-env-file)
    - [Explanation of Configuration Variables](#explanation-of-configuration-variables)
  - [3. Obtain Your Dokuly API Key](#3-obtain-your-dokuly-api-key)
  - [4. Set Up URL Configuration](#4-set-up-url-configuration)
  - [5. Include Theme and Drawing Sheet Paths](#5-include-theme-and-drawing-sheet-paths)
- [Usage](#usage)
  - [1. Open Your PCB Project](#1-open-your-pcb-project)
  - [2. Ensure Board Variables are Set](#2-ensure-board-variables-are-set)
    - [Setting Board Variables](#setting-board-variables)
  - [3. Use the Plugin](#3-use-the-plugin)
- [Troubleshooting](#troubleshooting)
- [Support](#support)
- [License](#license)

---

## Features

- Generate Gerber and Drill files from your KiCad PCB design.
- Export Schematic PDFs.
- Generate and upload BOM CSV files.
- Generate position files for SMD components.
- Upload files directly to Dokuly with a single click.

## Prerequisites

- **KiCad 8.0 or later** installed on your system.
- **Python 3** (comes bundled with KiCad).
- A **Dokuly account** with appropriate permissions.
- **Dokuly API Key** obtained from your Dokuly tenant.

## Installation

1. **Manual Installation via ZIP File:**

   - Download the latest version of the plugin as a ZIP file:
     [Download v1.0.0](https://github.com/Dokuly-PLM/kicad-to-dokuly-plugin/archive/refs/tags/v1.0.0.zip)
   - Extract the ZIP file contents to your KiCad plugins directory:

     - **Windows:** `C:\Users\<YourUsername>\Documents\KiCad\8.0\scripting\plugins\`
     - **macOS:** `/Users/<YourUsername>/Documents/KiCad/8.0/scripting/plugins/`
     - **Linux:** `/home/<YourUsername>/Documents/KiCad/8.0/scripting/plugins/`
    
     - **NOTE**: After extracting, rename the folder from `kicad-to-dokuly-plugin-1.0.0` to `kicad-to-dokuly-plugin` to avoid issues with KiCad’s plugin directory structure.

2. **Manual Installation via Git:**

   - Alternatively, clone the repository directly into the plugins directory:
     ```bash
     git clone https://github.com/Dokuly-PLM/kicad-to-dokuly-plugin.git <YourPluginDirectory>
     ```
   - Ensure the `<YourPluginDirectory>` matches the path of your KiCad plugins directory (as listed above).

3. **Verify Installation:**

   - After installation, you should see the Dokuly cloud icon in the KiCad toolbar.


## Configuration

Before using the plugin, you need to configure it by setting up a `.env` file and providing necessary details.

### 1. Locate the Plugin Folder

- **Windows:** `C:\Users\<YourUsername>\Documents\KiCad\8.0\scripting\plugins\kicad-to-dokuly-plugin`
- **macOS:** `/Users/<YourUsername>/Documents/KiCad/8.0/scripting/plugins/kicad-to-dokuly-plugin`
- **Linux:** `/home/<YourUsername>/Documents/KiCad/8.0/scripting/plugins/kicad-to-dokuly-plugin`

### 2. Create or Edit the `.env` File

In the `kicad-to-dokuly-plugin` folder, create a new file named `.env` (if it doesn't exist) and open it in a text editor.

#### Sample `.env` File for Windows

```ini
DOKULY_API_KEY=your_api_key_here
DOKULY_TENANT=your_tenant_name
DOKULY_URL=dokuly.com
URL_PROTOCOL=https
REPLACE_FILES=true
THEME_PATH=C:\Path\To\Your\Theme\someTemplate.json
DRAWING_SHEET_PATH=C:\Path\To\Your\DrawingSheet\someDrawingSheet.kicad_wks
```

**Note**: The same example works fine for Linux and MacOS, the only change necessary is to update the absolute paths for **THEME_PATH** and **DRAWING_SHEET_PATH**.

## Explanation of Configuration Variables

- **DOKULY_API_KEY:** Your Dokuly API Key obtained from the Dokuly admin page.
- **DOKULY_TENANT:** Your Dokuly tenant name (e.g., `tenant` for `tenant.dokuly.com`).
- **DOKULY_URL:** The Dokuly server URL. Use `dokuly.com` for the cloud-hosted version or your own domain if self-hosted.
- **URL_PROTOCOL:** Protocol to use (`http` or `https`). Use `https` for secure connections. Use `http` if self-hosted on local network.
- **REPLACE_FILES:** If true, the files on the PCBA will be overwritten with the new files. If false, files will not be overwritten.  
**Note**: We recommend having **REPLACE_FILES** set to true.
- **THEME_PATH:** Path to your KiCad theme file (e.g., `Theme.json`).
- **DRAWING_SHEET_PATH:** Path to your KiCad drawing sheet template file (e.g., `Sheet_Template.kicad_wks`).

**Note:**: The theme path and the drawing sheet path must be full paths. E.g. `C:\Users\SomeUser\kicad-libraries\Theme.json`.

### 3. Obtain Your Dokuly API Key

1. **Log in to Dokuly:**
    - Navigate to your Dokuly tenant URL (e.g., `https://your_tenant_name.dokuly.com`).
    - If using self-hosted or running on localhost, use your custom url.

2. **Access the Admin Page:**
    - Click on the **Administration** tab in the navigation menu.

3. **Navigate to API Keys:**
    - In the admin panel, go to the **API Keys** section.

4. **Create or Retrieve API Key:**
    - If you don't have an API key, create a new one.
    - Make sure it has access to the project that the PCBA is connected to.
    - Copy the API key.

5. **Update `.env` File:**
    - Replace `your_api_key_here` in your `.env` file with the API key you just copied.

### 4. Set Up URL Configuration

Depending on your Dokuly deployment, configure the following in your `.env` file:

- **For Dokuly Cloud Hosting:**

    ```ini
    DOKULY_URL=dokuly.com
    URL_PROTOCOL=https
    ```

- **For Local Testing or Self-Hosting:**

    ```ini
    DOKULY_URL=localhost:8000
    URL_PROTOCOL=http
    ```

    *(Adjust the port number if your local server runs on a different port.)*

- **For Custom Domain Hosting:**

    ```ini
    DOKULY_URL=yourdomain.com
    URL_PROTOCOL=https
    ```

### 5. Include Theme and Drawing Sheet Paths

Provide the paths to your KiCad theme and drawing sheet template files.

- **THEME_PATH:**
    - Path to your theme file (e.g., `theme.json`).

- **DRAWING_SHEET_PATH:**
    - Path to your drawing sheet template file (e.g., `sheet.kicad_wks`).

**Example Paths on Windows:**

```ini
THEME_PATH=C:\Users\YourUsername\nd-kicad-libraries\theme.json
DRAWING_SHEET_PATH=C:\Users\YourUsername\nd-kicad-libraries\sheet.kicad_wks
```

**Note:** Ensure that the paths are absolute and correctly point to the files on your system.

## Usage

### 1. Open Your PCB Project

Open the KiCad project containing your PCB design.

### 2. Ensure Board Variables are Set

The plugin relies on specific board variables to identify the PCBA and revision.

#### Setting Board Variables

- **Open PCB Editor:**
  - Open your PCB design in KiCad's PCB Editor.

- **Access Board Setup:**
  - Go to `File > Board Setup` or press `E` while hovering over the board.

- **Set Board Variables:**
  - Navigate to the **Text Variables** section.
  - Add the following variables:
    - **PCBA_NUMBER**: Set this to your PCBA number (e.g., `PCBA1234`, **Note**: This must be the dokuly PCBA number).
    - **PART_REVISION**: Set this to your revision identifier (e.g., `A`, **Note**: This must be the dokuly PCBA revision).

- **Save Changes:**
  - Click **OK** to save the board variables.

### 3. Use the Plugin

- **Launch the Plugin:**
  - In KiCad's PCB Editor, click on the **Dokuly Cloud** icon in the toolbar.

- **Verify PCBA Information:**
  - The plugin window will display the **PCBA_NUMBER** and **REVISION** extracted from your board variables.

- **Fetch PCBA from Dokuly:**
  - The plugin will attempt to fetch the PCBA item from Dokuly using the provided PCBA number and revision.
  - Check the output area in the plugin window for messages confirming the fetch operation.

- **Push PCBA to Dokuly:**
  - Click the **Push PCBA to Dokuly** button.
  - The plugin will:
    - Generate PCB PDFs for front and back.
    - Generate Gerber and Drill files.
    - Generate the Schematic PDF.
    - Generate the BOM CSV.
    - Generate Position files for SMD components.
    - Upload all generated files to Dokuly.
  - Monitor the output area for progress and any error messages.
  
    **WARNING**: While the upload and file generation is being processed, please do not click the **Push PCBA to Dokuly** button or close the plugin window.

- **Verify in Dokuly:**
  - Log in to your Dokuly account.
  - Navigate to the PCBA item to verify that the files have been uploaded and associated correctly.

## Troubleshooting

- **Plugin Not Appearing in Toolbar:**
  - Ensure that the plugin is installed in the correct directory.
  - Restart KiCad after installation.

- **Unable to Fetch PCBA:**
  - Verify that your `.env` file is correctly configured.
  - Ensure that the `PCBA_NUMBER` and `PART_REVISION` board variables are set.
  - Check your internet connection and API key validity.

- **File Generation Errors:**
  - Ensure that KiCad is installed correctly and that `kicad-cli` is accessible.
  - Verify the paths to the theme and drawing sheet files.

- **File Upload Failures:**
  - Check the output area for specific error messages.
  - Ensure that your Dokuly API key has the necessary permissions.

- **File Deletion Errors:**
  - The plugin may fail to delete temporary files if they are open in another program.
  - Ensure that no other applications are using the files.

## Support

If you encounter issues or have questions:

- **GitHub Issues:**
  - Report problems or suggestions on the plugin's GitHub repository issues page.

- **Contact Dokuly Support:**
  - For Dokuly-specific inquiries, contact Dokuly Support. More information on [dokuly](https://dokuly.com).

## License

This project is licensed under the GPL-3.0 License.

**Note:** This plugin is provided as-is. Always ensure you have backups of your data before performing operations that modify files or data.

---

### Additional Tips

- **Updating the `.env` File:**
  - Ensure there are no trailing spaces or hidden characters in your `.env` file.
  - Use absolute paths for `THEME_PATH` and `DRAWING_SHEET_PATH` to avoid issues.

- **Permissions:**
  - Make sure that the `.env` file and the plugin folder have the appropriate read/write permissions.

- **KiCad Variables:**
  - Double-check that `PCBA_NUMBER` and `PART_REVISION` are correctly set in your KiCad board variables. These are crucial for the plugin to function properly.

- **Testing:**
  - After setting up, perform a test upload with a sample PCB to ensure that all configurations are correct and the upload process works as expected.

Feel free to customize the README further to fit any additional details or specific instructions related to your plugin version or usage scenarios.
