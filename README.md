# Cassis-Verif

This repo contians the source code of *Cassis-Verif*, a tool developed as part of my master thesis at the University of Bern in Switzerland.  
*Cassis-Verif* aims to simplify formal verification of flight software by providing deep project insights and AI generated code explanations to the verification engineer. Additionally it provides an intuitive web based graphical user interface, which facilitates management of the formal verification proofs. It is a Single-User application that runs on Docker and can therefore be deployed to any environment that supports Docker. Multi-User scenarios can be implemented by spwaning multiple container instances and it supports build-time customization with project specific configurations and resources using presets.

## Project Structure

- The `app` folder contains both the Python FastAPI backend application and the HTML/JS frontend.
- The `doxygen` folder contains configuration and customization for doxygen docs used in the application.
- The `presets` folder contains presets that can be used when building the container image to pre-provision project specific configurations and resources (See [Presets](#presets)).
- The `scripts` folder contains a variety of scripts that are used inside the container.
- The `.env.example` file contains a list of all available environment variables with explanations.
- The `requirements.txt` file contains a list of all Python dependencies.

## How To Build & Run

Building the project requires a Docker installation.  
Note: When using the `cassis` preset, the first build might take well above 10 minutes! Also, the `cassis` build stage generates a lot of log output which might be clipped at some point. To see full log output while building, [disable buildkit](https://stackoverflow.com/questions/65819424/is-there-a-way-to-increase-the-log-size-in-docker-when-building-a-container).

- Start by cloning this repo and navigate into the project root using your preferred editor.
- Create a `.env` file in the project root (see `.env.example` for a list of all available env vars).
- Customize the `docker-compose.yaml` to your liking:
  - Select your preferred preset (See [Available Presets](#available-presets)).
  - Specify your preferred docker image, registry and tag.
- Run `docker compose build` to build the project into a Docker image.
- Run `docker compose up -d` to run the project in a Docker container.
- Run `docker compose down` to stop the running Docker container.

## Presets

Presets are used to customize the Docker image at build time, which allows pre-provisioning of project specific resources and configurations.

### Available Presets

Currently the following presets are available:

- **default**: The default preset, which offers no additional build stage or resources.
- **cassis**: The cassis preset, which pre-provisions the Colour and Stereo Sturface Imaging System (CaSSIS) flight software used on the ExoMars Trace Gas Orbiter. It includes the following features:
  - The cassis software design document PDF.
  - The cassis source code.
  - Prebuilt RTEMS sources.
  - Prebuilt AI Hints.
  - Preconfigured compiler flags for RTEMS.

### Custom Presets

Creating a custom preset consists of the following two steps:

- Creating a folder with the preset's name in the `presets` folder.
- Creating a build stage with the preset's name in the `Dockerfile`.

#### Preset Folder

At the very least, the preset folder must contain a json file called `project-defines.json` with the following structure:

```json
{
    "includes": [],
    "defines": [],
    "env": []
}
```

The `includes` array contains a list of directory paths, that should be used as compiler include paths (`-I` flags). These paths can use `$(SRCDIR)` or `$(PRESET_DIR)` to reference the corresponding directories.  
The `defines` array continas a list of compiler define directives (`-D` flags).  
The `env` array contains a list of key=value pairs that are added as environment variables.  
See the `project-defines.json` in the `cassis` preset for examples.

Optionally, the preset folder can contain the following files (Note: file names must match exactly):

- **sdd.pdf**: The software design document in PDF format.
- **src.tgz**: A gzip compressed tar archive containing the source code of the flight software.
- **hints.tgz**: A gzip compressed tar archive containing the prebuilt AI hints for the given flight software source code.
- **includes/*.tgz**: An includes directory containing multiple gzip compressed tar archives (e.g. third party dependencies).

#### Preset Build Stage

At the very least, the preset build stage must create an output folder in the containers root folder (`/output`). All the content of this output folder will be copied to the *Cassis-Verif* container's `preset` folder (preserving the origianl folder structure). From there it can be accessed like any other third party dependency (e.g. using the `project-defines.json` to pre-provision include directories). Other than that, the preset build stage can be used to build any kind of dependencies that require building from source (e.g. custom operating system files like ROTS). Check the `default` preset build stage for a minimal build stage.
