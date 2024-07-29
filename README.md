# Planalyst

## Build

The easiest way is to build an Apptainer container as follows:

```bash
apptainer build planalyst.sif Apptainer.planalyst
```

If you want to set up everything locally, you can find the necessary packages and build steps in the Apptainer.planalyst file.

## Running

Once the container is built, it directly executes the (planalyst.py)[scipts/planalyst.py] file, which has the following usage:

```
./planalyst.sif --help

usage: planalyst.py [-h] -i INSTANCE [-m {ddnnf-compiler,counting,enumeration,enumeration-no-write,interact}] [--domain DOMAIN] --horizon HORIZON [--write-plan-files] [--dump-output] [--cleanup] [--no-invariant-synthesis]

Count number of plans of a planning problem.

options:
  -h, --help            show this help message and exit
  -i INSTANCE, --instance INSTANCE
                        The path to the PDDL instance file.
  -m {ddnnf-compiler,counting,enumeration,enumeration-no-write,interact}, --method {ddnnf-compiler,counting,enumeration,enumeration-no-write,interact}
                        The method to run: 'counting' for model counting, 'ddnnf-compiler' for decision DNNF compilation, 'enumeration' for enumerating plans and writing them to disk, 'enumeration-no-write' for enumerating plans without writing to disk, and 'interact' for
                        an interactive session with ddnife where you can query reasoning tasks such as 'count' for counting, 'core' for backbone variables, or 'random l 10' to get 10 random assignments.
  --domain DOMAIN       (Optional) The path to the PDDL domain file. If none is provided, the system will try to automatically deduce it from the instance filename.
  --horizon HORIZON     Horizon used by Madagascar.
  --dump-output         dump the output of tools.
  --cleanup             Clean all CNF files in the folder after execution.
  --no-invariant-synthesis
                        Don't use invariant synthesis in Madagascar.
```

The interactive mode is a wrapper around the stream mode of the [ddnnife tool](https://github.com/SoftVarE-Group/d-dnnf-reasoner), passing input to the reasoner. 
Usage information can be found in the dedicated section of the [Readme](d-dnnf-reasoner/README.md).

## Licensing

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.  
It includes subcomponents that are distributed under their own respective licenses. Each subcomponent's license file can be found in its corresponding subdirectory.

For more information on the GPL-3.0 license, see the [LICENSE](LICENSE) file in the root directory of this repository.

## References

David Speck, Markus Hecher, Daniel Gnad, Johannes K. Fichte, Augusto B. Corrêa: Counting and Reasoning with Plans. AAAI 2025.
