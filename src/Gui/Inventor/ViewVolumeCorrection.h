// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <FCGlobal.h>

#include <Inventor/SbViewportRegion.h>
#include <Inventor/SbViewVolume.h>

class SoCamera;

namespace Gui
{

/** A camera's view volume, corrected for how the viewport maps onto it, paired with the
 * viewport it maps onto.
 *
 * A camera's own view volume is not what gets rendered: SoCamera::viewportMapping
 * decides how the volume meets a viewport that is a different shape. With the
 * default ADJUST_CAMERA and a viewport taller than it is wide, the volume is
 * expanded by 1/aspect - which is why a tall window shows more of the scene
 * instead of a squashed version of it. Projecting a point through the uncorrected
 * volume therefore lands somewhere the point was never drawn.
 *
 * \c viewport is the viewport the returned volume maps onto, which the CROP_VIEWPORT_*
 * modes narrow; project to pixels against that, not the original, and offset the result
 * by its getViewportOriginPixels() - the CROP modes recentre the region as well as
 * shrinking it, so its corner is not the window's corner.
 */
struct MappedView
{
    SbViewVolume volume;
    SbViewportRegion viewport;
};

/** Pairs \a camera's view volume, corrected for how it maps onto \a viewport, with the
 * (possibly narrowed) viewport it maps onto. See MappedView for why both are needed
 * together. \a camera is assumed to sit at the scene root with no transform in front of
 * it - Coin's own overload takes a model-matrix argument for the general case, but every
 * caller of this function has one.
 */
[[nodiscard]] GuiExport MappedView mappedViewVolume(
    const SoCamera& camera,
    const SbViewportRegion& viewport
);

}  // namespace Gui
