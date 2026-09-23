// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>
#include <set>

#include <Inventor/SbRotation.h>
#include <Inventor/SbVec3f.h>

#include <Gui/ViewCubeLayout.h>

namespace Layout = Gui::ViewCubeLayout;
using PickId = Layout::PickId;

namespace
{
constexpr float pi = std::numbers::pi_v<float>;

// Looking at FRONT: the camera's +z (towards the viewer) turned onto -y.
SbRotation frontView()
{
    return SbRotation(SbVec3f(1.0F, 0.0F, 0.0F), pi / 2.0F);
}

// The default isometric view, looking down from front-right-top.
SbRotation isoView()
{
    return SbRotation(SbVec3f(0.0F, 0.0F, 1.0F), SbVec3f(1.0F, -1.0F, 1.0F));
}

// A camera whose "towards the viewer" axis is exactly this direction (roll does not matter here).
SbRotation lookingFrom(const SbVec3f& towardsViewer)
{
    return SbRotation(SbVec3f(0.0F, 0.0F, 1.0F), towardsViewer);
}

int countNonZero(const SbVec3f& v)
{
    return (v[0] != 0.0F) + (v[1] != 0.0F) + (v[2] != 0.0F);
}
}  // namespace

TEST(ViewCubeLayout, everyCubePickIdLightsOneTwoOrThreeTilesOnTheRightFaces)
{
    int ids = 0;
    for (int raw = static_cast<int>(PickId::Front); raw <= static_cast<int>(PickId::RearBottomLeft);
         ++raw) {
        const auto id = static_cast<PickId>(raw);
        const SbVec3f dir = Layout::pickDirection(id);
        const int touching = countNonZero(dir);
        ASSERT_GE(touching, 1) << "no direction for pick id " << raw;
        ++ids;

        const std::vector<int> lit = Layout::tilesFor(id);
        EXPECT_EQ(static_cast<int>(lit.size()), touching) << "pick id " << raw;

        std::set<int> faces;
        for (int tile : lit) {
            const auto& t = Layout::tiles()[static_cast<size_t>(tile)];
            EXPECT_EQ(t.pickId, id);
            const SbVec3f n = Layout::faceNormal(t.face);
            EXPECT_GT(n.dot(dir), 0.0F) << "tile " << tile << " is on a face the id does not touch";
            faces.insert(static_cast<int>(t.face));
        }
        EXPECT_EQ(static_cast<int>(faces.size()), touching) << "two lit tiles share a face";
    }
    EXPECT_EQ(ids, 26);
}

TEST(ViewCubeLayout, everyTileMapsBackToExactlyOneCubePickId)
{
    std::array<int, 54> seen {};
    for (int raw = static_cast<int>(PickId::Front); raw <= static_cast<int>(PickId::RearBottomLeft);
         ++raw) {
        for (int tile : Layout::tilesFor(static_cast<PickId>(raw))) {
            ++seen[static_cast<size_t>(tile)];
        }
    }
    for (int i = 0; i < Layout::tileCount; ++i) {
        EXPECT_EQ(seen[static_cast<size_t>(i)], 1) << "tile " << i;
    }
}

TEST(ViewCubeLayout, directionAndPickIdRoundTrip)
{
    EXPECT_EQ(Layout::pickIdForDirection(SbVec3f(0, -1, 1)), PickId::FrontTop);
    EXPECT_EQ(Layout::pickIdForDirection(SbVec3f(1, -1, 1)), PickId::FrontTopRight);
    EXPECT_EQ(Layout::pickIdForDirection(SbVec3f(-1, 0, 1)), PickId::TopLeft);
    EXPECT_EQ(Layout::pickIdForDirection(SbVec3f(1, 1, 0)), PickId::RearRight);
    EXPECT_EQ(Layout::pickIdForDirection(SbVec3f(0, 0, 0)), PickId::None);
    EXPECT_EQ(Layout::pickDirection(PickId::Home), SbVec3f(0, 0, 0));
}

TEST(ViewCubeLayout, tileCornersRunCounterClockwiseFromOutside)
{
    for (const auto& t : Layout::tiles()) {
        const SbVec3f a = t.corners[1] - t.corners[0];
        const SbVec3f b = t.corners[2] - t.corners[1];
        EXPECT_GT(a.cross(b).dot(Layout::faceNormal(t.face)), 0.0F);
    }
}

TEST(ViewCubeLayout, bandsAreTwentyTwoPercentOfTheSide)
{
    // The first tile on TOP is its (-x, -y) corner: from -1 to -1 + 2 * 0.22.
    const auto& corner = Layout::tiles()[0];
    EXPECT_EQ(corner.face, PickId::Top);
    EXPECT_NEAR(corner.corners[0][0], -1.0F, 1e-6F);
    EXPECT_NEAR(corner.corners[1][0], -0.56F, 1e-6F);
}

TEST(ViewCubeLayout, faceOnMatchesWithinOneDegreeOnly)
{
    const float deg = pi / 180.0F;
    EXPECT_EQ(Layout::faceOn(SbRotation()), PickId::Top);
    EXPECT_EQ(Layout::faceOn(frontView()), PickId::Front);
    const auto tilted = [&](float degrees) {
        return lookingFrom(SbVec3f(std::sin(degrees * deg), -std::cos(degrees * deg), 0.0F));
    };
    EXPECT_EQ(Layout::faceOn(tilted(0.9F)), PickId::Front);
    EXPECT_EQ(Layout::faceOn(tilted(1.5F)), PickId::None);
    EXPECT_EQ(Layout::faceOn(isoView()), PickId::None);
}

TEST(ViewCubeLayout, faceShadeIsBrightestForTheFaceTowardsTheViewer)
{
    EXPECT_NEAR(Layout::faceShade(PickId::Front, frontView()), 1.0F, 1e-5F);
    EXPECT_NEAR(Layout::faceShade(PickId::Rear, frontView()), 0.85F, 1e-5F);
    EXPECT_GT(Layout::faceShade(PickId::Top, isoView()), 0.85F);
}

TEST(ViewCubeLayout, trianglesOnlyShowForAFaceOnView)
{
    const auto has = [](bool faceOn, PickId id) {
        for (const auto& r : Layout::controlRects(faceOn)) {
            if (r.pickId == id) {
                return true;
            }
        }
        return false;
    };
    for (PickId id : {PickId::ArrowNorth, PickId::ArrowSouth, PickId::ArrowEast, PickId::ArrowWest}) {
        EXPECT_TRUE(has(true, id));
        EXPECT_FALSE(has(false, id));
    }
    for (PickId id : {PickId::Home, PickId::ArrowLeft, PickId::ArrowRight, PickId::ViewMenu}) {
        EXPECT_TRUE(has(true, id));
        EXPECT_TRUE(has(false, id));
    }
    EXPECT_FALSE(has(true, PickId::Backside));
    EXPECT_EQ(Layout::controlAt(0.09F, 0.09F, false), PickId::Home);
    EXPECT_EQ(Layout::controlAt(0.5F, 0.15F, false), PickId::None);
    EXPECT_EQ(Layout::controlAt(0.5F, 0.15F, true), PickId::ArrowNorth);
}

TEST(ViewCubeLayout, trianglesClearTheFaceOnSquareInPerspective)
{
    // Perspective shows the face-on square at 0.232..0.768 of the overlay (ortho: 0.262..0.738).
    for (const auto& r : Layout::controlRects(true)) {
        const bool clear = r.right < 0.232F || r.left > 0.768F || r.bottom < 0.232F || r.top > 0.768F;
        EXPECT_TRUE(clear) << "control " << static_cast<int>(r.pickId) << " overlaps the face";
    }
}

TEST(ViewCubeLayout, controlsStayOutsideTheIsometricSilhouette)
{
    // An isometric cube reaches sqrt(3) / 2.1 / 2 = 0.4124 of the overlay from its centre.
    const float reach = std::sqrt(3.0F) / 2.1F / 2.0F;
    for (const auto& r : Layout::controlRects(false)) {
        const float nx = std::clamp(0.5F, r.left, r.right);
        const float ny = std::clamp(0.5F, r.top, r.bottom);
        EXPECT_GT(std::hypot(nx - 0.5F, ny - 0.5F), reach)
            << "control " << static_cast<int>(r.pickId) << " sits on the cube";
    }
}
