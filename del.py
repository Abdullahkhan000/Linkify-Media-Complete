import os
import shutil

current_folder = os.getcwd()

for name in os.listdir(current_folder):
    path = os.path.join(current_folder, name)
    
    base, ext = os.path.splitext(name)

    if base.lower().endswith(" copy"):
        print(f"Deleting: {name}")

        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

print("Done.")