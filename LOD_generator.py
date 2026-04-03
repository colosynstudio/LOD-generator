bl_info = {
    "name": "LOD Generator (Unreal and Unity Ready)",
    "author": "ColosynStudio",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > LOD Gen",
    "description": "Batch LOD generation and export for Unreal and Unity",
    "category": "Object",
}

from pathlib import Path
import re
import bpy
from bpy.props import IntProperty, FloatProperty, PointerProperty, BoolProperty, StringProperty
from bpy.types import PropertyGroup, Operator, Panel


# ─────────────────────────────────────────────
#  Scene-level settings
# ─────────────────────────────────────────────
class LODSettings(PropertyGroup):
    num_lods: IntProperty(
        name="Number of LODs",
        description="How many LOD levels to generate (excluding LOD0)",
        min=1,
        max=6,
        default=3,
    )
    
    unreal_mode: BoolProperty(
        name="unreal export",
        description= "Enable Unreal Naming Convention and property",
        default= True
    )

    lod_1_keep: FloatProperty(name="LOD1", min=0.01, max=0.99, default=0.75, subtype='FACTOR')
    lod_2_keep: FloatProperty(name="LOD2", min=0.01, max=0.99, default=0.50, subtype='FACTOR')
    lod_3_keep: FloatProperty(name="LOD3", min=0.01, max=0.99, default=0.30, subtype='FACTOR')
    lod_4_keep: FloatProperty(name="LOD4", min=0.01, max=0.99, default=0.15, subtype='FACTOR')
    lod_5_keep: FloatProperty(name="LOD5", min=0.01, max=0.99, default=0.08, subtype='FACTOR')
    lod_6_keep: FloatProperty(name="LOD6", min=0.01, max=0.99, default=0.04, subtype='FACTOR')
    
    file_path: StringProperty(
         name= "File Path",
         description= "Choose file path to export ",
         subtype="DIR_PATH"
    )
    
    make_folder: BoolProperty(
         name="Make folder",
         description = "Make folder for each LOD group",
         default = True
    )
    
def get_keep_values(settings):
     return [
        settings.lod_1_keep,
        settings.lod_2_keep,
        settings.lod_3_keep,
        settings.lod_4_keep,
        settings.lod_5_keep,
        settings.lod_6_keep,
    ]
    
LOD_PROP_NAMES = [
    "lod_1_keep",
    "lod_2_keep",
    "lod_3_keep",
    "lod_4_keep",
    "lod_5_keep",
    "lod_6_keep",
]


# ─────────────────────────────────────────────
#  Main Operator
# ─────────────────────────────────────────────
class LOD_OT_Generate(Operator):
    bl_idname = "object.lod_generate"
    bl_label = "High poly mesh detected. Generate LODs anyway?"
    bl_description = "Generate LODs for all selected mesh objects"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    high_poly_warning: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):
        
        try:
           prefs = context.preferences.addons[__name__].preferences
           threshold = prefs.poly_threshold
        except KeyError:
           threshold = 100000
    
        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']
    
        has_high_poly = any(len(o.data.polygons) > threshold for o in selected_meshes)
    
        if has_high_poly :
          return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)
    

    def execute(self, context):
        settings = context.scene.lod_settings
        num_lods = settings.num_lods
        keep_values = get_keep_values(settings)
        

        # Only process mesh objects
        selected_meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not selected_meshes:
            self.report({'WARNING'}, "No mesh objects selected. Select at least one mesh.")
            return {'CANCELLED'}

        processed = 0
        
        
       
        for obj in selected_meshes:
            
            zero_poly = len(obj.data.polygons) == 0
            
            if zero_poly :
                self.report({'WARNING'}, f"{obj.name} has zero geometry")
                continue
                
          
            
            
            original_name = obj.name
            world_matrix = obj.matrix_world.copy()
            
            #────Filtering lod, source and high poly to skip ──────────────────────
            if re.search(r"_LOD\d+|_Source$|_HIGH$", original_name,flags=re.IGNORECASE):
              self.report({'WARNING'}, "skipped LOD, source and high poly ")
              continue
          
            original_name = re.sub(r"_LOW$","", original_name,flags=re.IGNORECASE)
          
          
            if settings.unreal_mode:
             stripped = re.sub(r"^SM_","", original_name,flags=re.IGNORECASE)
             original_name = "SM_" + stripped
             
            obj.name = f"{obj.name}_Source"
            
            #──── Creating collections ──────────────────────
            if not "source" in bpy.data.collections:
             source_col = bpy.data.collections.new("source")
             bpy.context.scene.collection.children.link(source_col)
            else:
             source_col =bpy.data.collections["source"]
            
            
            if not "LOD" in bpy.data.collections:
              LOD_col = bpy.data.collections.new("LOD")
              bpy.context.scene.collection.children.link(LOD_col)
            else:
              LOD_col = bpy.data.collections["LOD"]
            
            old_collection = list(obj.users_collection)
            
            if obj.name not in source_col.objects:
             source_col.objects.link(obj)
            
            for col in old_collection:
                if col != source_col:
                 col.objects.unlink(obj)
            
            layer_col = bpy.context.view_layer.layer_collection.children.get("source")
            
            if layer_col:
                layer_col.hide_viewport = True
            

                
            # ── 1. Create Empty parent ──────────────────────────────────
            empty = bpy.data.objects.new(original_name, None)
            empty.empty_display_type = 'PLAIN_AXES'
            empty.empty_display_size = 0.5
            context.collection.objects.link(empty)
            # Place empty at object's world origin
            empty.matrix_world = world_matrix
            
            old_collection = list(empty.users_collection)
            
            if empty.name not in LOD_col.objects:
             LOD_col.objects.link(empty)
                
            for col in old_collection:
                if col != LOD_col: 
                 col.objects.unlink(empty)

            if settings.unreal_mode:
                 empty["fbx_type"] = "LodGroup"

            # ── 3 Making LOD0, parent to empty ──────────────
            lod0 = obj.copy()
            lod0.data = obj.data.copy()
            lod0.name=f"{original_name}_LOD0"
            context.collection.objects.link(lod0)
            lod0.parent= empty
            lod0.matrix_parent_inverse = empty.matrix_world.inverted()
            
            old_collection = list(lod0.users_collection)
            if lod0.name not in LOD_col.objects:
                LOD_col.objects.link(lod0)
            
            for col in old_collection:
                if col != LOD_col: 
                  col.objects.unlink(lod0)

            

            # ── 4. Generate LOD1 … LODn ─────────────────────────────────
            for i in range(num_lods):
                # User sets how much geometry to KEEP directly (0.75 = keep 75%)
                keep_ratio = getattr(settings, LOD_PROP_NAMES[i])  if i < len(keep_values) else 0.5

                # Duplicate from LOD0 mesh data (always from original)
                lod_obj = lod0.copy()
                lod_obj.data = lod0.data.copy()
                lod_obj.name = f"{original_name}_LOD{i + 1}"
                context.collection.objects.link(lod_obj)
                
                old_collection = list(lod_obj.users_collection)
                if lod_obj.name not in LOD_col.objects:
                 LOD_col.objects.link(lod_obj)
            
                for col in old_collection:
                    if col != LOD_col: 
                     col.objects.unlink(lod_obj)
                

                # Add Decimate modifier but DON'T apply — keep it live so user can tweak later
                dec = lod_obj.modifiers.new(name="LOD_Decimate", type='DECIMATE')
                dec.ratio = max(0.01, keep_ratio)  # clamp to avoid 0 (full collapse)
                dec.use_collapse_triangulate = True
                # Parent to empty, preserve world position
                lod_obj.parent = empty
                lod_obj.matrix_parent_inverse = empty.matrix_world.inverted()

            processed += 1
            
       
            
            
        # Restore selection to empties for clarity
        for o in bpy.data.objects:
           o.select_set(False)
        self.report({'INFO'}, f"✓ LODs generated for {processed} object(s)")
        return {'FINISHED'}

# ─────────────────────────────────────────────
# Export Operator
# ─────────────────────────────────────────────

class LOD_OT_EXPORT(Operator):
    bl_idname = "object.lod_export"
    bl_label = "No selection. Export all LOD groups?"
    bl_description = "Export LOD groups as fbx"
    bl_options = {'REGISTER', 'UNDO'}
    
    #──── No selection popup ──────────────────────
    def invoke(self, context, event):
     if len(context.selected_objects) == 0:
        return context.window_manager.invoke_confirm(self, event, )
     return self.execute(context)
    
    def execute(self, context):
        settings = context.scene.lod_settings
        filepath = Path(settings.file_path)
        makefolder = settings.make_folder
        
        if len(settings.file_path) == 0:
            self.report({"WARNING"}, "No File path selected")
            return {"CANCELLED"}
        
        #──── Checking if LOD collection exist and if any LOD group in it ──────────────────────     
        if  not "LOD"  in bpy.data.collections:
            self.report({"WARNING"}, f" LOD collection doesn't exist")
            return {'CANCELLED'}
        
        if len(bpy.data.collections["LOD"].objects) == 0:
            self.report({"WARNING"}, f"LOD collection empty")
            return {'CANCELLED'}
        
        #──── Saving original selection and active selection ──────────────────────
        original_selection = context.selected_objects[:]
        original_active = context.view_layer.objects.active
        
        empties_to_export = set() 
        
        exported = 0
         
        #──── Adding  empty to set to process export ──────────────────────
        for o in context.selected_objects:
           if o.type == 'EMPTY':
             empties_to_export.add(o)
           elif o.type == 'MESH':
               if o.parent is not None:
                empties_to_export.add(o.parent)
              
        if len(original_selection) > 0 and len(empties_to_export) == 0:
            self.report ({'WARNING'}, "Non LOD group selected")
            return {'CANCELLED'}    
              
        if len(empties_to_export) == 0 :
          for o in bpy.data.collections["LOD"].objects:
            if o.type == 'EMPTY':
              empties_to_export.add(o) 
            
        for o in bpy.data.objects:
           o.select_set(False)
           
        #──── Selecting all children of empty ──────────────────────   
        for obj in empties_to_export:
            original_location = obj.location.copy()
            obj.location = (0, 0, 0)
            obj.select_set(True)
            for y in obj.children:
                y.select_set(True)
            context.view_layer.objects.active = obj
            
            if len(obj.children) == 0:
                self.report({'WARNING'},f"{obj.name} has no LOD(s)")
                obj.location = original_location
                continue
            
            #──── Exporting path logic ──────────────────────
            if makefolder:
                folder_file = filepath / f"{obj.name}"
                folder_file.mkdir(exist_ok=True)
                export_path = folder_file /  f"{obj.name}.FBX"
            else:
                export_path = filepath / f"{obj.name}.FBX"
                
            if export_path.exists():
                self.report({'WARNING'},f"{obj.name}.fbx already exists, overwriting")
                
    
                            #──── Unreal export settings ──────────────────────   
            if settings.unreal_mode:
                bpy.ops.export_scene.fbx(
                       filepath=str(export_path),
                       use_selection=True,
                       axis_forward='-Y',
                       axis_up='Z',
                       use_custom_props=True,
                       use_triangles=True,
                       apply_unit_scale=True,
                       bake_space_transform=True,
                       mesh_smooth_type= 'FACE'
                      )
                      
            #──── Unity export settings ──────────────────────         
            else:
                 bpy.ops.export_scene.fbx(
                       filepath=str(export_path),
                       use_selection=True,
                       axis_forward='Z',
                       axis_up='Y',
                       use_custom_props=False,
                       use_triangles=True,
                       apply_unit_scale=True,
                       )   
                       
            obj.location = original_location
            for o in bpy.data.objects:
               o.select_set(False)
               
            exported += 1
            
            
        for o in  original_selection:
             o.select_set(True)
             
        context.view_layer.objects.active =original_active 
         
        self.report({'INFO'}, f"Exported {exported} group(s)")
        return {'FINISHED'}
 




# ─────────────────────────────────────────────
#  UI Panel
# ─────────────────────────────────────────────
class LOD_PT_Panel(Panel):
    bl_label = "LOD Generator"
    bl_idname = "LOD_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'LOD Gen'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.lod_settings
       

        # ── Settings ────────────────────────────────────────────────────
        box = layout.box()
        box.label(text="Settings", icon='SETTINGS')
        box.prop(settings, "num_lods")
        box.prop(settings, "unreal_mode")

        # ── LOD Level Sliders ────────────────────────────────────────────
        box2 = layout.box()
        box2.label(text="Geometry to Keep per LOD", icon='MOD_DECIM')

        col = box2.column(align=True)
        for i in range(settings.num_lods):
            if i < len(LOD_PROP_NAMES):
                row = col.row(align=True)
                keep = round(getattr(settings, LOD_PROP_NAMES[i]) * 100, 1)
                row.label(text=f"LOD{i + 1}  ({keep}% geometry)")
                row.prop(settings, LOD_PROP_NAMES[i], text="Keep", slider=True)
                
        # ── Info ─────────────────────────────────────────────────────────
        layout.separator()
        info = layout.box()
        info.label(text="Select mesh(es) then generate", icon='INFO')
        info.label(text="Empty = LodGroup parent for UE5")

        # ── Operator Button ──────────────────────────────────────────────
        layout.separator()
        layout.operator("object.lod_generate", text="Generate LODs", icon='MESH_DATA')
        
        #─── Export panel ──────────────────────────────────────────────
        layout.separator()
        box3 = layout.box()
        box3.label(text="Export LOD", icon="EXPORT")
        box3.prop(settings, "file_path")
        box3.prop(settings, "make_folder")
        
        if settings.unreal_mode:
            layout.separator()
            layout.operator("object.lod_export", text="Export for unreal", icon='EXPORT')
        else:
            layout.separator()
            layout.operator("object.lod_export", text="Export for unity", icon='EXPORT')
            
            
# ─────────────────────────────────────────────
#  AddonPreferances operantor
# ─────────────────────────────────────────────
            
class LODAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__  # matches the addon module name

    poly_threshold: IntProperty(
        name="High Poly Threshold",
        description="Polygon count above which a warning is shown before generating LODs",
        default=100000,
        min=1000,
        soft_max=1000000,
    )

    def draw(self, prefs):
        self.layout.prop(self, "poly_threshold")
            


# ─────────────────────────────────────────────
#  Register / Unregister
# ─────────────────────────────────────────────
classes = [
    LODSettings,
    LOD_OT_Generate,
    LOD_PT_Panel,
    LOD_OT_EXPORT,
    LODAddonPreferences,
    
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.lod_settings = PointerProperty(type=LODSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.lod_settings

if __name__ == "__main__":
    register()
