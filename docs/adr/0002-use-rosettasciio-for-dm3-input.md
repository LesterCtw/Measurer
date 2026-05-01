# Use RosettaSciIO for DM3 Input

Measurer will use `rosettasciio` as the first `.dm3` image input library. This matches the existing Denoiser project direction and avoids writing a custom DigitalMicrograph parser, while accepting that company `.dm3` metadata scale handling remains best effort until real sample files are tested.
