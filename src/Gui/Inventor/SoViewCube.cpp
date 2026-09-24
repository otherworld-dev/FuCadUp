// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 FuCadUp contributors
// SPDX-FileNotice: Part of the FreeCAD project.

/******************************************************************************
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the     *
 *   License, or (at your option) any later version.                          *
 *                                                                            *
 *   FreeCAD is distributed in the hope that it will be useful, but           *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of               *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            *
 *   GNU Lesser General Public License for more details.                      *
 *                                                                            *
 *   You should have received a copy of the GNU Lesser General Public         *
 *   License along with FreeCAD.  If not, see                                *
 *   <https://www.gnu.org/licenses/>.                                         *
 *                                                                            *
 ******************************************************************************/

#include <FCConfig.h>

#ifdef FC_OS_WIN32
# include <windows.h>
#endif

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <numbers>
#include <vector>

#include <Inventor/SoPickedPoint.h>
#include <Inventor/actions/SoGLRenderAction.h>
#include <Inventor/actions/SoRayPickAction.h>
#include <Inventor/details/SoFaceDetail.h>
#include <Inventor/elements/SoDepthBufferElement.h>
#include <Inventor/elements/SoGLShaderProgramElement.h>
#include <Inventor/elements/SoGLTextureEnabledElement.h>
#include <Inventor/elements/SoLazyElement.h>
#include <Inventor/elements/SoLightModelElement.h>
#include <Inventor/elements/SoOverrideElement.h>
#include <Inventor/elements/SoShapeStyleElement.h>
#include <Inventor/elements/SoTextureQualityElement.h>
#include <Inventor/elements/SoViewportRegionElement.h>
#include <Inventor/misc/SoState.h>
#include <Inventor/nodes/SoDepthBuffer.h>
#include <Inventor/nodes/SoDrawStyle.h>
#include <Inventor/nodes/SoFaceSet.h>
#include <Inventor/nodes/SoIndexedFaceSet.h>
#include <Inventor/nodes/SoIndexedLineSet.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoMaterialBinding.h>
#include <Inventor/nodes/SoOrthographicCamera.h>
#include <Inventor/nodes/SoPerspectiveCamera.h>
#include <Inventor/nodes/SoPickStyle.h>
#include <Inventor/nodes/SoPolygonOffset.h>
#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoShapeHints.h>
#include <Inventor/nodes/SoSwitch.h>
#include <Inventor/nodes/SoTexture2.h>
#include <Inventor/nodes/SoTransform.h>
#include <Inventor/nodes/SoVertexProperty.h>
#include <Inventor/system/gl.h>

#include "SoViewCube.h"
#include "ViewCubeLayout.h"

using namespace Gui;

SO_NODE_SOURCE(SoViewCube);

namespace
{

namespace Layout = Gui::ViewCubeLayout;

// The overlay projection, the depth-clear helpers and beginOverlayPass below are copied
// from SoNaviCube.cpp, which stays unedited so that upstream merges into it stay clean.
constexpr float overlayNear = 0.1F;
constexpr float overlayFar = 10.1F;
constexpr float overlayOrthoExtent = 2.1F;
constexpr float overlayFovScale = 1.1F;
constexpr float overlayCubeZ = -5.1F;

constexpr float guideAlphaScale = 0.16F;
constexpr float hiliteAlphaScale = 0.70F;
constexpr int hiliteMaterial = 6;  // materials 0..5 are the six face shades

/** Restores the OpenGL state touched while clearing the overlay depth. */
class ScopedDepthClearState
{
public:
    ScopedDepthClearState()
    {
        scissorEnabled = glIsEnabled(GL_SCISSOR_TEST);
        glGetIntegerv(GL_SCISSOR_BOX, scissorBox);
        glGetBooleanv(GL_DEPTH_WRITEMASK, &depthWriteMask);
        glGetDoublev(GL_DEPTH_CLEAR_VALUE, &clearDepth);
    }

    ScopedDepthClearState(const ScopedDepthClearState&) = delete;
    ScopedDepthClearState& operator=(const ScopedDepthClearState&) = delete;

    ~ScopedDepthClearState() noexcept
    {
        glScissor(
            scissorBox[0],
            scissorBox[1],
            static_cast<GLsizei>(scissorBox[2]),
            static_cast<GLsizei>(scissorBox[3])
        );
        if (scissorEnabled == GL_TRUE) {
            glEnable(GL_SCISSOR_TEST);
        }
        else {
            glDisable(GL_SCISSOR_TEST);
        }
        glDepthMask(depthWriteMask);
        glClearDepth(clearDepth);
    }

private:
    GLboolean scissorEnabled {GL_FALSE};
    GLint scissorBox[4] {};
    GLboolean depthWriteMask {GL_TRUE};
    GLdouble clearDepth {1.0};
};

/** Clears only the depth buffer in the cube's viewport, leaving colour untouched. */
void clearOverlayDepth(int x, int y, int width, int height)
{
    if (width <= 0 || height <= 0) {
        return;
    }
    ScopedDepthClearState state;
    glEnable(GL_SCISSOR_TEST);
    glScissor(x, y, static_cast<GLsizei>(width), static_cast<GLsizei>(height));
    glDepthMask(GL_TRUE);
    glClearDepth(1.0);
    glClear(GL_DEPTH_BUFFER_BIT);
}

float transparency(float alpha)
{
    return 1.0F - std::clamp(alpha, 0.0F, 1.0F);
}

SoVertexProperty* makeVertices(const std::vector<SbVec3f>& points)
{
    auto* vp = new SoVertexProperty;
    vp->vertex.setValues(0, static_cast<int>(points.size()), points.data());
    return vp;
}

}  // namespace

void SoViewCube::initClass()
{
    SO_NODE_INIT_CLASS(SoViewCube, SoShape, "Shape");
}

SoViewCube::SoViewCube()
{
    SO_NODE_CONSTRUCTOR(SoViewCube);
    SO_NODE_ADD_FIELD(size, (1.0F));
    SO_NODE_ADD_FIELD(opacity, (1.0F));
    SO_NODE_ADD_FIELD(borderWidth, (1.0F));
    SO_NODE_ADD_FIELD(baseColor, (SbColor(0.165F, 0.165F, 0.165F)));
    SO_NODE_ADD_FIELD(baseAlpha, (0.72F));
    SO_NODE_ADD_FIELD(emphaseColor, (SbColor(0.659F, 0.659F, 0.659F)));
    SO_NODE_ADD_FIELD(emphaseAlpha, (1.0F));
    SO_NODE_ADD_FIELD(hiliteColor, (SbColor(0.024F, 0.588F, 0.843F)));
    SO_NODE_ADD_FIELD(hiliteAlpha, (1.0F));
    SO_NODE_ADD_FIELD(hiliteId, (static_cast<int>(PickId::None)));
    SO_NODE_ADD_FIELD(cameraOrientation, (SbRotation()));
    SO_NODE_ADD_FIELD(cameraIsOrthographic, (TRUE));
    SO_NODE_ADD_FIELD(viewportRect, (SbVec4f(0.0F, 0.0F, 0.0F, 0.0F)));
    SO_NODE_ADD_FIELD(controlsOpacity, (0.0F));
    SO_NODE_ADD_FIELD(controlsLive, (FALSE));
}

SoViewCube::~SoViewCube()
{
    // The label textures are ref'd here as well as by the scene graph.
    for (LabelNodes& nodes : labels) {
        if (nodes.texture) {
            nodes.texture->unref();
            nodes.texture = nullptr;
        }
    }
    if (pickRoot) {
        pickRoot->unref();
    }
    if (sceneRoot) {
        sceneRoot->unref();
    }
}

int SoViewCube::labelSlot(PickId face) const
{
    const auto& faces = Layout::mainFaces();
    const auto it = std::find(faces.begin(), faces.end(), face);
    return it == faces.end() ? -1 : static_cast<int>(it - faces.begin());
}

void SoViewCube::ensureSceneGraph() const
{
    if (sceneRoot) {
        return;
    }
    sceneRoot = new SoSeparator;
    sceneRoot->ref();
    pickRoot = new SoSeparator;
    pickRoot->ref();

    cameraSwitch = new SoSwitch;
    auto* ortho = new SoOrthographicCamera;
    auto* persp = new SoPerspectiveCamera;
    for (SoCamera* cam : {static_cast<SoCamera*>(ortho), static_cast<SoCamera*>(persp)}) {
        cam->viewportMapping = SoCamera::LEAVE_ALONE;
        cam->aspectRatio = 1.0F;
        cam->position = SbVec3f(0.0F, 0.0F, 0.0F);
        cam->orientation = SbRotation();
        cam->nearDistance = overlayNear;
        cam->farDistance = overlayFar;
        cam->focalDistance = std::abs(overlayCubeZ);
    }
    ortho->height = 2.0F * overlayOrthoExtent;
    persp->heightAngle
        = 2.0F * std::atan(std::tan(std::numbers::pi_v<float> / 8.0F) * overlayFovScale);
    cameraSwitch->addChild(ortho);
    cameraSwitch->addChild(persp);
    cameraSwitch->whichChild = 0;

    auto* filled = new SoDrawStyle;
    filled->style = SoDrawStyle::FILLED;

    auto* cube = new SoSeparator;
    buildCube(cube);

    sceneRoot->addChild(cameraSwitch);
    sceneRoot->addChild(filled);
    sceneRoot->addChild(cube);
    buildControls(sceneRoot);

    pickRoot->addChild(cameraSwitch);
    pickRoot->addChild(cube);
}

void SoViewCube::buildCube(SoSeparator* cube) const
{
    auto* depth = new SoDepthBuffer;
    depth->test = TRUE;
    depth->write = TRUE;
    depth->function = SoDepthBuffer::LEQUAL;
    cube->addChild(depth);

    rootTransform = new SoTransform;
    cube->addChild(rootTransform);

    // Tiles: one quad each, coloured per tile so an edge or corner can light across faces.
    {
        auto* sep = new SoSeparator;
        tileMaterial = new SoMaterial;
        sep->addChild(tileMaterial);
        auto* binding = new SoMaterialBinding;
        binding->value = SoMaterialBinding::PER_FACE_INDEXED;
        sep->addChild(binding);
        auto* offset = new SoPolygonOffset;  // push the faces back so lines draw on top
        offset->factor = 1.0F;
        offset->units = 1.0F;
        sep->addChild(offset);
        auto* hints = new SoShapeHints;
        hints->vertexOrdering = SoShapeHints::COUNTERCLOCKWISE;
        hints->shapeType = SoShapeHints::SOLID;  // cull the far faces of the see-through cube
        hints->faceType = SoShapeHints::CONVEX;
        sep->addChild(hints);

        std::vector<SbVec3f> points;
        std::vector<int32_t> index;
        for (const auto& tile : Layout::tiles()) {
            const auto base = static_cast<int32_t>(points.size());
            for (int i = 0; i < 4; ++i) {
                points.push_back(tile.corners[static_cast<size_t>(i)]);
                index.push_back(base + i);
            }
            index.push_back(-1);
        }
        tileFaces = new SoIndexedFaceSet;
        auto* vp = makeVertices(points);
        vp->materialBinding = SoVertexProperty::PER_FACE_INDEXED;
        tileFaces->vertexProperty = vp;
        tileFaces->coordIndex.setValues(0, static_cast<int>(index.size()), index.data());
        tileFaces->materialIndex.setNum(Layout::tileCount);
        sep->addChild(tileFaces);
        cube->addChild(sep);
    }

    const auto addLines = [cube](SoMaterial*& material, SoDrawStyle** style,
                                 const std::vector<SbVec3f>& points) {
        auto* sep = new SoSeparator;
        material = new SoMaterial;
        sep->addChild(material);
        auto* drawStyle = new SoDrawStyle;
        drawStyle->lineWidth = 1.0F;
        sep->addChild(drawStyle);
        if (style) {
            *style = drawStyle;
        }
        std::vector<int32_t> index;
        for (int32_t i = 0; i + 1 < static_cast<int32_t>(points.size()); i += 2) {
            index.insert(index.end(), {i, i + 1, -1});
        }
        auto* lines = new SoIndexedLineSet;
        lines->vertexProperty = makeVertices(points);
        lines->coordIndex.setValues(0, static_cast<int>(index.size()), index.data());
        sep->addChild(lines);
        cube->addChild(sep);
    };

    {
        // Guide lines: the borders of each face's centre tile, run out to the face's edges.
        // Tile row*3+col has corners (col,row) (col+1,row) (col+1,row+1) (col,row+1).
        std::vector<SbVec3f> guides;
        const auto& t = Layout::tiles();
        for (size_t f = 0; f < 6; ++f) {
            const size_t base = f * Layout::tilesPerFace;
            for (size_t col : {size_t {1}, size_t {2}}) {  // the two inner column borders
                guides.push_back(t[base + col].corners[0]);
                guides.push_back(t[base + 6 + col].corners[3]);
            }
            for (size_t row : {size_t {1}, size_t {2}}) {  // the two inner row borders
                guides.push_back(t[base + row * 3].corners[0]);
                guides.push_back(t[base + row * 3 + 2].corners[1]);
            }
        }
        addLines(guideMaterial, nullptr, guides);
    }

    {
        // The cube's 12 edges: every pair of corners that differ on one axis.
        const auto corner = [](int bits) {
            return SbVec3f(
                (bits & 1) ? 1.0F : -1.0F,
                (bits & 2) ? 1.0F : -1.0F,
                (bits & 4) ? 1.0F : -1.0F
            );
        };
        std::vector<SbVec3f> edges;
        for (int a = 0; a < 8; ++a) {
            for (int bit : {1, 2, 4}) {
                if (!(a & bit)) {
                    edges.push_back(corner(a));
                    edges.push_back(corner(a | bit));
                }
            }
        }
        addLines(edgeMaterial, &edgeStyle, edges);
    }

    // Labels on each face's centre tile, drawn over the face and never picked.
    {
        auto* group = new SoSeparator;
        auto* depthLabels = new SoDepthBuffer;
        depthLabels->test = TRUE;
        depthLabels->write = FALSE;
        depthLabels->function = SoDepthBuffer::LEQUAL;
        group->addChild(depthLabels);
        auto* offset = new SoPolygonOffset;
        offset->factor = -1.0F;
        offset->units = -1.0F;
        group->addChild(offset);
        auto* unpickable = new SoPickStyle;
        unpickable->style = SoPickStyle::UNPICKABLE;
        group->addChild(unpickable);

        for (size_t f = 0; f < 6; ++f) {
            LabelNodes& nodes = labels[f];
            nodes.visible = new SoSwitch;
            nodes.visible->whichChild = SO_SWITCH_NONE;  // until setLabelImage gives it text
            nodes.material = new SoMaterial;
            nodes.visible->addChild(nodes.material);
            if (!nodes.texture) {
                nodes.texture = new SoTexture2;
                nodes.texture->ref();
                nodes.texture->wrapS = SoTexture2::CLAMP;
                nodes.texture->wrapT = SoTexture2::CLAMP;
                nodes.texture->model = SoTexture2::MODULATE;  // white text tinted by the material
                nodes.texture->enableCompressedTexture = FALSE;
            }
            nodes.visible->addChild(nodes.texture);
            const auto& centre = Layout::tiles()[f * Layout::tilesPerFace + 4].corners;
            auto* vp = makeVertices(std::vector<SbVec3f>(centre.begin(), centre.end()));
            vp->texCoord.setNum(4);
            vp->texCoord.set1Value(0, SbVec2f(0.0F, 0.0F));
            vp->texCoord.set1Value(1, SbVec2f(1.0F, 0.0F));
            vp->texCoord.set1Value(2, SbVec2f(1.0F, 1.0F));
            vp->texCoord.set1Value(3, SbVec2f(0.0F, 1.0F));
            auto* quad = new SoFaceSet;
            quad->numVertices.set1Value(0, 4);
            quad->vertexProperty = vp;
            nodes.visible->addChild(quad);
            group->addChild(nodes.visible);
        }
        cube->addChild(group);
    }
}

void SoViewCube::buildControls(SoSeparator* /*parent*/) const
{}

void SoViewCube::setLabelImage(
    PickId id,
    const SbVec2s& imageSize,
    int numComponents,
    const unsigned char* pixels
)
{
    ensureSceneGraph();
    const int slot = labelSlot(id);
    if (slot < 0) {
        return;
    }
    LabelNodes& nodes = labels[static_cast<size_t>(slot)];
    if (!pixels || imageSize[0] <= 0 || imageSize[1] <= 0 || numComponents <= 0) {
        nodes.visible->whichChild = SO_SWITCH_NONE;
        return;
    }
    nodes.texture->image.setValue(imageSize, numComponents, pixels, SoSFImage::COPY);
    nodes.visible->whichChild = SO_SWITCH_ALL;
    touch();
}

void SoViewCube::clearLabelTextures()
{
    for (LabelNodes& nodes : labels) {
        if (nodes.visible) {
            nodes.visible->whichChild = SO_SWITCH_NONE;
        }
    }
}

void SoViewCube::updateSceneGraph() const
{
    ensureSceneGraph();

    const float op = std::clamp(opacity.getValue(), 0.0F, 1.0F);
    const SbRotation cam = cameraOrientation.getValue();
    cameraSwitch->whichChild = cameraIsOrthographic.getValue() ? 0 : 1;
    rootTransform->rotation = cam.inverse();
    rootTransform->translation = SbVec3f(0.0F, 0.0F, overlayCubeZ);

    const SbColor base = baseColor.getValue();
    tileMaterial->diffuseColor.setNum(hiliteMaterial + 1);
    tileMaterial->transparency.setNum(hiliteMaterial + 1);
    for (int f = 0; f < 6; ++f) {
        const float shade = Layout::faceShade(Layout::mainFaces()[static_cast<size_t>(f)], cam);
        tileMaterial->diffuseColor.set1Value(f, base * shade);
        tileMaterial->transparency.set1Value(f, transparency(baseAlpha.getValue() * op));
    }
    tileMaterial->diffuseColor.set1Value(hiliteMaterial, hiliteColor.getValue());
    tileMaterial->transparency.set1Value(
        hiliteMaterial,
        transparency(hiliteAlpha.getValue() * hiliteAlphaScale * op)
    );

    const auto hilite = static_cast<PickId>(hiliteId.getValue());
    const std::vector<int> lit = Layout::tilesFor(hilite);
    int32_t* index = tileFaces->materialIndex.startEditing();
    for (int i = 0; i < Layout::tileCount; ++i) {
        const bool on = std::find(lit.begin(), lit.end(), i) != lit.end();
        index[i] = on ? hiliteMaterial : i / Layout::tilesPerFace;
    }
    tileFaces->materialIndex.finishEditing();

    const SbColor emphase = emphaseColor.getValue();
    guideMaterial->diffuseColor = emphase;
    guideMaterial->transparency = transparency(emphaseAlpha.getValue() * guideAlphaScale * op);
    edgeMaterial->diffuseColor = emphase;
    edgeMaterial->transparency = transparency(emphaseAlpha.getValue() * op);
    edgeStyle->lineWidth = std::max(1.0F, borderWidth.getValue());
    for (LabelNodes& nodes : labels) {
        nodes.material->diffuseColor = emphase;
        nodes.material->transparency = transparency(emphaseAlpha.getValue() * op);
    }
}

int SoViewCube::hilitedTileCount() const
{
    updateSceneGraph();
    int count = 0;
    for (int i = 0; i < Layout::tileCount; ++i) {
        count += tileFaces->materialIndex[i] == hiliteMaterial ? 1 : 0;
    }
    return count;
}

SoViewCube::PickId SoViewCube::pickAt(const SbVec2s& point) const
{
    updateSceneGraph();

    const SbVec4f& rect = viewportRect.getValue();
    const float width = rect[2];
    const float height = rect[3];
    if (width <= 0.0F || height <= 0.0F) {
        return PickId::None;
    }
    const SbVec2s local(
        static_cast<short>(static_cast<float>(point[0]) - rect[0]),
        static_cast<short>(static_cast<float>(point[1]) - rect[1])
    );
    if (local[0] < 0 || local[1] < 0 || local[0] >= static_cast<short>(width)
        || local[1] >= static_cast<short>(height)) {
        return PickId::None;
    }

    if (controlsLive.getValue()) {
        const float x = (static_cast<float>(local[0]) + 0.5F) / width;
        const float y = 1.0F - (static_cast<float>(local[1]) + 0.5F) / height;
        const bool faceOnView = Layout::faceOn(cameraOrientation.getValue()) != PickId::None;
        const PickId control = Layout::controlAt(x, y, faceOnView);
        if (control != PickId::None) {
            return control;
        }
    }

    SoRayPickAction pick(SbViewportRegion(static_cast<short>(width), static_cast<short>(height)));
    pick.setPoint(local);
    pick.setRadius(1.0F);
    pick.apply(pickRoot);
    const SoPickedPoint* hit = pick.getPickedPoint();
    if (!hit || !hit->getPath() || hit->getPath()->getTail() != tileFaces) {
        return PickId::None;
    }
    const SoDetail* detail = hit->getDetail();
    if (!detail || !detail->isOfType(SoFaceDetail::getClassTypeId())) {
        return PickId::None;
    }
    const int tile = static_cast<const SoFaceDetail*>(detail)->getFaceIndex();
    if (tile < 0 || tile >= Layout::tileCount) {
        return PickId::None;
    }
    return Layout::tiles()[static_cast<size_t>(tile)].pickId;
}

void SoViewCube::beginOverlayPass(SoGLRenderAction* action, int x, int y, int width, int height)
{
    SoState* state = action->getState();

    // As in SoNaviCube::beginOverlayPass: ignore the viewer's overrides, draw unlit and blended.
    SoOverrideElement::setDiffuseColorOverride(state, this, FALSE);
    SoOverrideElement::setTransparencyOverride(state, this, FALSE);
    SoOverrideElement::setLightModelOverride(state, this, FALSE);
    SoOverrideElement::setMaterialBindingOverride(state, this, FALSE);
    SoOverrideElement::setColorIndexOverride(state, this, FALSE);
    SoOverrideElement::setDrawStyleOverride(state, this, FALSE);
    SoGLTextureEnabledElement::disableAll(state);
    SoLazyElement::setColorMaterial(state, FALSE);
    SoGLShaderProgramElement::enable(state, FALSE);
    SoShapeStyleElement::setVertexArrayRendering(state, TRUE);
    SoShapeStyleElement::setTransparentMaterial(state, TRUE);
    SoShapeStyleElement::setTransparentTexture(state, TRUE);
    SoShapeStyleElement::setTransparencyType(state, SoGLRenderAction::BLEND);
    SoLazyElement::setTransparencyType(state, SoGLRenderAction::BLEND);

    SbViewportRegion vp = SoViewportRegionElement::get(state);
    vp.setViewportPixels(x, y, width, height);
    SoViewportRegionElement::set(state, vp);

    // Reset depth inside the cube's viewport so it self-occludes whatever the scene left there.
    clearOverlayDepth(x, y, width, height);
    SoDepthBufferElement::set(state, TRUE, TRUE, SoDepthBufferElement::LEQUAL, SbVec2f(0.0F, 1.0F));
    glEnable(GL_DEPTH_TEST);
    glDepthMask(GL_TRUE);
    glDepthFunc(GL_LEQUAL);
    glDepthRange(0.0, 1.0);

    SoLightModelElement::set(state, this, SoLightModelElement::BASE_COLOR);
    SoShapeStyleElement::setLightModel(state, SoLazyElement::BASE_COLOR);
    SoLazyElement::setLightModel(state, SoLazyElement::BASE_COLOR);
    SoLazyElement::enableBlending(state, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    SoLazyElement::setVertexOrdering(state, SoLazyElement::CCW);
    SoLazyElement::setTwosideLighting(state, FALSE);
}

void SoViewCube::GLRender(SoGLRenderAction* action)
{
    if (!action || !shouldGLRender(action)) {
        return;
    }
    const SbVec4f& rect = viewportRect.getValue();
    const int x = static_cast<int>(std::lround(rect[0]));
    const int y = static_cast<int>(std::lround(rect[1]));
    const int width = static_cast<int>(std::lround(rect[2]));
    const int height = static_cast<int>(std::lround(rect[3]));
    if (width <= 0 || height <= 0) {
        return;
    }
    updateSceneGraph();

    SoState* state = action->getState();
    state->push();
    beginOverlayPass(action, x, y, width, height);
    SoTextureQualityElement::set(state, this, 1.0F);
    sceneRoot->GLRender(action);
    SoGLTextureEnabledElement::disableAll(state);
    state->pop();
}

void SoViewCube::generatePrimitives(SoAction* /*action*/)
{}

void SoViewCube::computeBBox(SoAction* /*action*/, SbBox3f& box, SbVec3f& center)
{
    const float half = size.getValue() * 0.5F;
    box.setBounds(SbVec3f(-half, -half, -half), SbVec3f(half, half, half));
    center.setValue(0.0F, 0.0F, 0.0F);
}
