#! python3

# DO NOT EDIT THIS FILE DIRECTLY. This is generated from a literate program of
# this script with the help of the Literate Programming extension for Visual
# Studio Code written by Nathan Letwory.
#
# If you want to contribute install the Literate Programming extension for
# Visual Studio Code from
# https://marketplace.visualstudio.com/items?itemName=jesterking.literate and
# edit the .literate files in this repository instead.
#
# The source code repository is at https://github.com/jesterKing/rhildraw
#
# The code, literate and generated, is licensed under MIT license. See
# https://github.com/jesterKing/rhildraw/LICENSE for more details.
#
# Or you can read the HTML rendered documentation at
# https://jesterking.github.io/rhildraw
#

import scriptcontext as sc
import math

from typing import Mapping, List

import Rhino

from Rhino.Geometry import Transform, Mesh, Vector3f, Point3f
from Rhino.Display import Color4f
from Rhino.DocObjects import ObjectAttributes, ObjectMaterialSource
from Rhino.DocObjects import InstanceDefinition
from Rhino.Render import ChildSlotNames, ContentUuids, RenderContentType

PbrNames = ChildSlotNames.PhysicallyBased
rhmath = Rhino.RhinoMath

from System.IO import DirectoryInfo, Directory, File, FileInfo
from System.IO import EnumerationOptions, SearchOption

from pathlib import Path

class LDrawFile:
    def __init__(self, path : Path, data : List[str] = []):
        self.commands = data
        self.path = path
        self.name = path.name
        self.suffix = path.suffix
        self.pname = f"{path.parent.name}\\{self.name}"
    def get_commands(self):
        if len(self.commands)==0:
            with self.path.open(encoding="utf-8") as f:
                cmds = [l.strip() for l in f.readlines()]
                cmds = [c for c in cmds if len(c) > 0]
                self.commands = cmds
    
        return self.commands
    def contains_poly_commands(self):
        cmds = self.get_commands()
        for cmd in cmds:
            if len(cmd) == 0: continue
            if cmd[0] in ("2", "3", "4", "5"):
                return True
    
        return False

class LDrawMaterial:
    def __init__(self, props):
        self.properties = props
        self.name = props["COLOUR"]
        self.render_material = None

    def _get_color4f(self, colstr):
        colstr = colstr[1:]
        r = int(colstr[0:2], 16) / 255.0
        g = int(colstr[2:4], 16) / 255.0
        b = int(colstr[4:6], 16) / 255.0
        return Color4f(r, g, b, 1.0)

    def _alpha(self, alphastr):
        alpha = 1.0 - (float(alphastr) / 255.0)
        return alpha

    def get_render_material(self):
        if self.render_material == None:

            raise Exception(f"Material non-existant: {self.name}")
        return self.render_material

    def create_render_material(self):
        for rm in sc.doc.RenderMaterials:
            if rm.Name == self.name:
                self.render_material = rm
                return
        pbr_rm = RenderContentType.NewContentFromTypeId(pbr_guid)

        _basecolor = self._get_color4f(self.properties["VALUE"])

        _roughness = 0.2
        _metallic = 0.0
        _opacity = 1.0

        if "ALPHA" in self.properties:
            _opacity = self._alpha(self.properties["ALPHA"])
            _roughness = 0.03

        if "METAL" in self.properties or "CHROME" in self.properties:
            _metallic = 1.0
            _roughness = 0.03
        if "MATTE_METALLIC" in self.properties:
            _metallic = 1.0
            _roughness = 0.3

        pbr_rm.SetParameter(PbrNames.BaseColor, _basecolor)
        pbr_rm.SetParameter(PbrNames.Opacity, _opacity)
        pbr_rm.SetParameter(PbrNames.Metallic, _metallic)
        pbr_rm.SetParameter(PbrNames.Roughness, _roughness)

        pbr_rm.Name = self.name
        self.render_material = pbr_rm
        sc.doc.RenderMaterials.Add(pbr_rm)

class LDrawXform:
    def __init__(self, data : str):
        data = data.strip()
        if len(data) > 0:
            try:
                d = [float(f) for f in data.split()[2:14]]
                self.x = d[0]
                self.y = d[1]
                self.z = d[2]
                self.a = d[3]
                self.b = d[4]
                self.c = d[5]
                self.d = d[6]
                self.e = d[7]
                self.f = d[8]
                self.g = d[9]
                self.h = d[10]
                self.i = d[11]
                xform : Transform = Transform.Identity
                xform.M00 = self.a
                xform.M01 = self.b
                xform.M02 = self.c
                xform.M03 = self.x
                xform.M10 = self.d
                xform.M11 = self.e
                xform.M12 = self.f
                xform.M13 = self.y
                xform.M20 = self.g
                xform.M21 = self.h
                xform.M22 = self.i
                xform.M23 = self.z
                self.xform = xform
            except Exception as e:
                self.xform = Transform.Identity
        else:
            self.xform = Transform.Identity

    def set_xform(self, xform):
        self.xform = xform

    def transform_point(self, u : float, v : float, w : float):
        p = Point3f(u, v, w)
        p.Transform(self.xform)
        return [p.X, p.Y, p.Z]

    def get_xform(self):
        return self.xform

rhino_orient = LDrawXform("")
rhino_orient.set_xform(
    Transform.Rotation(
        rhmath.ToRadians(-90.0),
        Vector3f.XAxis,
        Point3f.Origin
    )
)
id_xform = LDrawXform("")

def apply_transforms(v, xforms):
    for xform in xforms:
        v = xform.transform_point(*v)
    return v

def collate_transforms(xforms):
   xform = Transform.Identity
   for _xform in xforms:
       xform = xform * _xform.get_xform()

   return xform


# Globals
vfiles: Mapping[str, LDrawFile]= dict()
idefs : Mapping[str, InstanceDefinition]= dict()
materials : Mapping[str, LDrawMaterial]= dict()
vertidx = 0
zoom_extents = False
pbr_guid = ContentUuids.PhysicallyBasedMaterialType

def refresh(zoom_extents = False):
    sc.doc.Views.Redraw()
    if zoom_extents:
        Rhino.RhinoApp.RunScript("ZEA", False)
    Rhino.RhinoApp.Wait()

def clean_name(part_name):
    part_name = part_name.removesuffix(".dat")
    part_name = part_name.removesuffix(".DAT")
    part_name = part_name.removesuffix(".ldr")
    part_name = part_name.removesuffix(".LDR")
    return part_name

def prepare_parts_dictionary():
    global lib_path
    library_path : Path = Path(lib_path)
    library_path_net : DirectoryInfo = DirectoryInfo(lib_path)
    all_parts_net = library_path_net.EnumerateFiles("*", SearchOption.AllDirectories)
    for p in all_parts_net:
        fn = Path(p.FullName)
        ldrawfile = LDrawFile(fn)
        vfiles[ldrawfile.name] = ldrawfile
        vfiles[ldrawfile.pname] = ldrawfile
def add_virtual_file(model : Path, filename : str, data : List[str]):
    virtual_file_path = model.parent / 'virtual' / filename
    virtual_file = LDrawFile(virtual_file_path, data)
    vfiles[virtual_file.name] = virtual_file
    vfiles[virtual_file.pname] = virtual_file

def prepare_idefs_dictionary():
    for idef in sc.doc.InstanceDefinitions:
        idefs[idef.Name] = idef
def update_idefs_dictionary(part_name):
    idef_part_name = clean_name(part_name)
    idef = sc.doc.InstanceDefinitions.Find(idef_part_name)
    if idef:
        idefs[idef_part_name] = idef
        return idef
    return None
def get_part_idef(prt):
    p = Path(prt)
    pname = clean_name(p.name)
    if pname in idefs:
        return idefs[pname]

    return None
def get_ldraw_file(part_name : str) -> LDrawFile:
    global vfiles

    part_name = part_name.replace('/', '\\')

    if part_name in vfiles:
        return vfiles[part_name]

    raise Exception(f"Part file not found: {part_name}")

def add_poly(m : Mesh, cmd : str, xforms : list):
    global vertidx
    stride = 3
    start = 2
    vertices = int(cmd[0])
    elements = vertices * stride
    to = start + vertices * stride
    d = cmd.split()[start:to]
    try:
        d = [float(f) for f in d]
    except Exception:
        return
    for i in range(0, elements, stride):
        V = apply_transforms(d[i:i+stride], xforms)
        m.Vertices.Add(*V)
        vertidx = vertidx + 1
    if vertices == 4:
        m.Faces.AddFace(vertidx - 4, vertidx - 3, vertidx - 2, vertidx - 1)
    elif vertices == 3:
        m.Faces.AddFace(vertidx - 3, vertidx - 2, vertidx - 1)
def load_geomety_from_file(part : LDrawFile, m : Mesh, xforms : list):
    cmds = part.get_commands()
    for cmd in cmds:
        if cmd.startswith('1'):
            d = cmd.split()
            xform = LDrawXform(cmd)
            prt = ' '.join(d[14:])
            _xforms = [xform] + xforms[:]
            try:
                part_file = get_ldraw_file(prt)
            except Exception:
                print(f"\tERR: Failed getting part {prt}, skipping")
                continue
            load_geomety_from_file(part_file, m, _xforms)
        elif cmd.startswith('3') or cmd.startswith('4'):
            add_poly(m, cmd, xforms)


def add_geometry(part_name : str):
    global vertidx
    vertidx = 0
    name = clean_name(part_name)

    existing_idef = sc.doc.InstanceDefinitions.Find(name)
    if existing_idef:
        print(f"\tSkipping {part_name}, instance already created")
        return
    tmesh = Mesh()
    mesh = Mesh()
    obattr = ObjectAttributes()

    obattr.Name = name
    obattr.Visible = True
    obattr.MaterialSource = ObjectMaterialSource.MaterialFromParent

    ldraw_file = get_ldraw_file(part_name)
    load_geomety_from_file(ldraw_file, tmesh, [id_xform])
    tmesh.Normals.ComputeNormals()
    tmesh.Compact()

    meshes = tmesh.SplitDisjointPieces()
    for submesh in meshes:
        submesh.Weld(rhmath.ToRadians(60))
        submesh.UnifyNormals()
        mesh.Append(submesh)
    mesh.Weld(rhmath.ToRadians(60))
    mesh.Compact()

    if mesh.Vertices.Count > 0 and mesh.Faces.Count > 0:
        sc.doc.InstanceDefinitions.Add(obattr.Name, "", Point3f.Origin, mesh, obattr)

def load_assembly(part : LDrawFile, xforms : list):
    cmds = []
    cmds = part.get_commands()

    cmds = [l for l in cmds if len(l)>0]
    for cmd in cmds:
        if cmd.startswith('1'):
            d = cmd.split()
            color_code = d[1]
            materials[color_code].create_render_material()
            rm = materials[color_code].render_material
            xform = LDrawXform(cmd)
            prt = ' '.join(d[14:])
            _xforms = xforms[:] + [xform]

            obattr = ObjectAttributes()
            obattr.Name = clean_name(prt)
            obattr.Visible = True
            obattr.MaterialSource = ObjectMaterialSource.MaterialFromObject
            obattr.RenderMaterial = rm

            if prt.lower().endswith(".ldr"):
                ldr_file = get_ldraw_file(prt)
                if ldr_file.contains_poly_commands():
                    add_geometry(prt)
                    idef = update_idefs_dictionary(prt)
                    if idef != None:
                        xform = collate_transforms(_xforms)
                        sc.doc.Objects.AddInstanceObject(idef.Index, xform, obattr)
                    else:
                        print(f"Couldn't add part {prt}")
                else:
                    load_assembly(ldr_file, _xforms)
            else:
                idef = get_part_idef(prt)
                xform = collate_transforms(_xforms)
                if idef != None:
                    sc.doc.Objects.AddInstanceObject(idef.Index, xform, obattr)
                else:
                    add_geometry(prt)
                    idef = update_idefs_dictionary(prt)
                    if idef != None:
                        sc.doc.Objects.AddInstanceObject(idef.Index, xform, obattr)
                    else:
                        print(f"Failed to add part {prt}")

            refresh(zoom_extents)
def load_model(model : LDrawFile):
    lines = model.get_commands()

    FILE_START = '0 FILE '
    first_file = ''
    if model.suffix.lower() == '.mpd':
        # parse file into virtual, read files
        cur_file = ''
        file_data = []
        for l in lines:
            if l.startswith(FILE_START):
                if cur_file != '':
                    add_virtual_file(model.path, cur_file, file_data)
                if cur_file == '':
                    first_file = l[len(FILE_START):]
                cur_file = l[len(FILE_START):]
                file_data = [l]
            else:
                file_data.append(l)
        add_virtual_file(model.path, cur_file, file_data) # last file
    start_part = get_ldraw_file(first_file)

    load_assembly(start_part, [rhino_orient])

def load_colors():
    colorldr = get_ldraw_file("LDConfig.ldr")
    cmds = colorldr.get_commands()
    COLOR_CMD = "0 !COLOUR "
    TO_REMOVE = "0 !"
    for cmd in cmds:
        if cmd.startswith(COLOR_CMD):
            properties = dict()
            cmd = cmd[len(TO_REMOVE):]
            cmd_split = cmd.split()
            if len(cmd_split) % 2 == 1:
                cmd_split.append('dummy')
            keyvalue_count = len(cmd_split) // 2
            for i in range(0, keyvalue_count*2, 2):
                properties[cmd_split[i]] = cmd_split[i+1]
            ldraw_material = LDrawMaterial(properties)
            materials[properties["CODE"]] = ldraw_material
    print("Colors read")

# If you want to see the model "build" while
# the script imports comment the following line
# out, or set every False to True
#sc.doc.Views.EnableRedraw(False, False, False)

###########################################
## Set path to where your LDraw library and
## model files are. They should be under
## the same main folder
## Use always forward slashes, also for
## folders on Windows
###########################################
#lib_path = "/Users/jesterking/Documents/brickdat/ldraw"
lib_path = "e:/dev/brickdat/ldraw"

prepare_parts_dictionary()
prepare_idefs_dictionary()
load_colors()

zoom_extents = True # Set to True to always see the whole model during import

###########################################
## Specify what model to load. Use just the
## file name (including extension)
###########################################
fl : Path = vfiles["10030-1.mpd"]
load_model(fl)

refresh(zoom_extents)

sc.doc.Views.EnableRedraw(True, True, True)

Rhino.RhinoApp.RunScript("ZEA", False)

print("Done")



